#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读采集 git 未提交改动，为 commit-message-assistant 提供生成素材。

安全约束：仅调用只读 git 子命令（rev-parse / diff / ls-files / show）和读取文件，
绝不执行 add/commit/push 等任何改变仓库状态的命令。

采集基准：传入仓库子目录时自动定位仓库根（--show-toplevel，只读白名单内），
后续 git 调用与文件读取全部以仓库根为基准，保证路径语义统一。

上下文保护：行数截断 + 字节帽双保险——行数截断防长 diff，
字节帽防"单行超大文件"（压缩 JSON / minified JS）在行数规则下漏网。

相似组检测：路径数字归一化后同模式且数量达标的文件视为同一批量操作产物
（如按年份切割出的 data/2015.json ... data/2024.json），输出 SIMILAR_GROUP
标记；组内代表文件详列、其余仅留文件名，供上层聚合为一条 commit message。
新增/修改/改名三组对称支持离群详列：成员体量（行数/diff 行数）与代表相差
悬殊（>2× 或 <½）时转为详列并统一标注，避免整组语义被代表文件掩盖。
"""
import os
import re
import sys
import subprocess

# Windows 下系统 Python 的 stdout 可能是 GBK：强制 UTF-8，避免输出进 agent 时乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 截断 / 阈值参数
LARGE_DIFF_LINES = 200      # tracked 文件 diff 超过此行数则截断
KEEP_DIFF_LINES = 80        # 截断后保留的前 N 行
UNTRACKED_FULL_LINES = 300  # 新文件行数 <= 此值则读全文
KEEP_UNTRACKED_LINES = 80   # 新文件截断后保留的前 N 行
MAX_BODY_BYTES = 16384      # 文件体（diff/新文件内容）字节上限；防单行大文件撑爆上下文
MANY_FILES = 50             # 改动文件超过此数则加提醒
SIMILAR_GROUP_MIN = 3       # 同模式文件达到此数则标记为相似组（建议聚合为一条 message）

# 相似组离群成员的统一标注（新增/修改/改名三组共用，上层按此识别"已详列"）
OUTLIER_NOTE = "  [相似组，离群，已详列]"

# Windows 编码：强制 git 输出 UTF-8
_GIT_ENV = dict(os.environ)
_GIT_ENV.setdefault("GIT_EDITOR", "true")
if sys.platform == "win32":
    _GIT_ENV["LC_ALL"] = "C.UTF-8"
    _GIT_ENV.setdefault("LANG", "en_US.UTF-8")


def git(args, cwd):
    p = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_GIT_ENV,
    )
    return p.returncode, p.stdout, p.stderr


def is_binary(raw):
    return b"\x00" in raw[:8192]


def parse_name_status(out):
    """解析 `git diff HEAD --name-status -z` 输出。
    返回 [(letter, path1, path2_or_None), ...]，path2 仅对 R/C 有值（新路径）。
    """
    entries = []
    parts = out.split("\0")
    i = 0
    n = len(parts)
    while i < n:
        s = parts[i]
        if not s:
            i += 1
            continue
        letter = s[0]
        if letter in ("R", "C"):
            if i + 2 < n:
                entries.append((letter, parts[i + 1], parts[i + 2]))
                i += 3
            else:
                i += 1
        else:
            if i + 1 < n:
                entries.append((letter, parts[i + 1], None))
                i += 2
            else:
                i += 1
    return entries


def trunc_lines(text, limit, keep):
    lines = text.splitlines()
    if len(lines) > limit:
        return "\n".join(lines[:keep]) + f"\n…(省略 {len(lines) - keep} 行)"
    return text


def trunc_bytes(text):
    """字节帽：文件体超过 MAX_BODY_BYTES 字节则截前 N 字节。
    行数截断防不住"单行超大文件"（整份压缩 JSON 只占 1 行，行数远小于阈值），
    故所有进入输出的体内容最终都要过这道帽。按字节切片后以
    errors="ignore" 解码，自动丢弃尾部残缺的多字节序列（UTF-8 边界安全）。
    """
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= MAX_BODY_BYTES:
        return text
    return (
        raw[:MAX_BODY_BYTES].decode("utf-8", errors="ignore")
        + f"\n…(超 {MAX_BODY_BYTES // 1024}KB 已截断)"
    )


def is_outlier(ln, rep_ln):
    """相似组离群判据：成员体量 >2× 或 <½ 代表即离群。
    ln/rep_ln 任一无效（<=0，如二进制/读取失败）则不算离群。
    三组（新增按行数、修改/改名按 diff 行数）共用同一规则。
    """
    return rep_ln > 0 and ln > 0 and (ln > 2 * rep_ln or 2 * ln < rep_ln)


def path_pattern(path):
    """路径数字归一化：把路径中所有数字串替换为 #，作为批量产物的组键。
    data/2015.json 与 data/2016.json → data/#.json；目录带序号的
    data/2015/index.json → data/#/index.json，同样能聚到一组。
    """
    return re.sub(r"\d+", "#", path)


def find_similar_groups(paths):
    """按归一化模式聚类，返回 {pattern: [成员路径，字母序]}。
    只保留成员数 >= SIMILAR_GROUP_MIN 的组；两个文件的巧合同模式不值得聚合。
    """
    buckets = {}
    for p in paths:
        buckets.setdefault(path_pattern(p), []).append(p)
    return {k: sorted(v) for k, v in buckets.items() if len(v) >= SIMILAR_GROUP_MIN}


def maybe_group_banner(path, groups, printed):
    """相似组第一个成员输出前打标记行，返回该组列表；非组成员返回 None。"""
    pat = path_pattern(path)
    grp = groups.get(pat)
    if grp and pat not in printed:
        printed.add(pat)
        print(
            f"\n>> SIMILAR_GROUP: {pat} ×{len(grp)}"
            "（同构批量文件，建议聚合为一条 commit message）"
        )
    return grp


def diff_for(path, cwd):
    """返回 (body, is_binary)。body 为 git diff 文本或空串。"""
    rc, out, _ = git(["diff", "HEAD", "--", path], cwd)
    if rc != 0:
        return "", False
    if "Binary files" in out or "GIT binary patch" in out:
        return "", True
    return out, False


def head_line_count(path, cwd):
    """返回文件在 HEAD 中的行数（用于删除文件摘要）。失败返回 -1。
    用 `HEAD:./path` 而非 `HEAD:path`：./ 前缀明确是树内路径，
    避免路径含冒号等特殊字符时的解析歧义。
    """
    rc, out, _ = git(["show", f"HEAD:./{path}"], cwd)
    if rc != 0:
        return -1
    return len(out.splitlines())


def read_newfile(path, cwd):
    """读新文件（staged-A 或 untracked）内容。返回 (body, total_lines, kind)。
    kind ∈ {FULL, TRUNC, BINARY, ERROR}。
    """
    full = os.path.join(cwd, path)
    try:
        with open(full, "rb") as f:
            head = f.read(8192)
            if is_binary(head):
                return "", 0, "BINARY"
            f.seek(0)
            raw = f.read()
    except Exception as e:
        return str(e), 0, "ERROR"
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    total = len(lines)
    if total <= UNTRACKED_FULL_LINES:
        return text, total, "FULL"
    return "\n".join(lines[:KEEP_UNTRACKED_LINES]), total, "TRUNC"


def collect(cwd):
    rc, out, _ = git(["rev-parse", "--is-inside-work-tree"], cwd)
    if rc != 0 or out.strip() != "true":
        print("NOT_A_REPO")
        return

    # 子目录调用扶正：定位仓库根，后续 git 调用与文件读取全部以根为基准。
    # git diff 的输出路径本就相对仓库根，而 ls-files 相对当前目录——
    # 统一切到根，两组路径语义才能对齐，REPO: 行也不会误导。
    rc, root, _ = git(["rev-parse", "--show-toplevel"], cwd)
    if rc == 0 and root.strip():
        cwd = os.path.abspath(root.strip())

    # tracked 改动（相对 HEAD 的净变更；-M 强制重命名检测，不依赖全局 diff.renames 配置）
    tracked = []
    rc, out, _ = git(["diff", "-M", "HEAD", "--name-status", "-z"], cwd)
    if rc == 0:
        tracked = parse_name_status(out)
    else:
        # 无 HEAD（全新仓库），用 --cached 取 index 与空 tree 的差异
        rc3, out3, _ = git(["diff", "-M", "--cached", "--name-status", "-z"], cwd)
        if rc3 == 0:
            tracked = parse_name_status(out3)

    rc2, out2, _ = git(["ls-files", "--others", "--exclude-standard", "-z"], cwd)
    untracked = [p for p in out2.split("\0") if p] if rc2 == 0 else []

    # 合并冲突权威判定：`git diff HEAD` 会把未解决冲突的文件伪装成普通 M（U 只在
    # --cached/status 视角出现），主路径解析永远看不到 U。改用 ls-files --unmerged
    # （只读白名单内）枚举冲突路径——其 -z 输出为 "<mode> <hash> <stage>\t<path>"
    # 全格式，且同一文件按 stage 1/2/3 出现三次，须按 tab 取末字段并去重。
    # 冲突文件同时从普通分组剔除——其 diff 是 ^^^^^^^ 组合格式，不该进"修改"组。
    unmerged_set = set()
    rc4, out4, _ = git(["ls-files", "--unmerged", "-z"], cwd)
    if rc4 == 0:
        for entry in out4.split("\0"):
            if entry:
                unmerged_set.add(entry.rsplit("\t", 1)[-1])

    news, mods, dels, rens, unmerged = [], [], [], [], []
    for letter, p1, p2 in tracked:
        if p1 in unmerged_set:
            continue  # 冲突文件单独成组，不进新增/修改/删除/改名
        if letter == "A":
            news.append((p1,))
        elif letter == "D":
            dels.append((p1,))
        elif letter in ("R", "C"):
            rens.append((p1, p2 or p1))
        else:  # M 及 T/X 等少见，归入修改
            mods.append((p1,))
    for p in untracked:
        if p in unmerged_set:
            continue
        news.append((p,))
    unmerged = sorted(unmerged_set)

    total = len(news) + len(mods) + len(dels) + len(rens)
    print(f"REPO: {os.path.abspath(cwd)}")
    print(f"TOTAL: {total}")
    if unmerged:
        print(f"WARN: {len(unmerged)} 个文件存在未解决的合并冲突，请先解决再提交")
    if total == 0 and not unmerged:
        print("NO_CHANGES")
        return
    if total > MANY_FILES:
        print(f"WARN: 改动较多({total} 个)，请逐条核对")

    # 新增（相似组成员预读一次，用于代表/离群详列判断）
    print("\n=== 新增 ===")
    news_sorted = sorted(news, key=lambda x: x[0])
    news_groups = find_similar_groups([e[0] for e in news_sorted])
    news_cache = {}
    for members in news_groups.values():
        for p in members:
            news_cache[p] = read_newfile(p, cwd)
    printed_news = set()
    for entry in news_sorted:
        p = entry[0]
        grp = maybe_group_banner(p, news_groups, printed_news)
        if p in news_cache:
            body, total_ln, k = news_cache[p]
        else:
            body, total_ln, k = read_newfile(p, cwd)
        if k == "BINARY":
            print(f"\n## [新增] {p}  (binary)")
            print("(binary, 内容跳过)")
        elif k == "ERROR":
            print(f"\n## [新增] {p}  (读取失败)")
            print(body)
        else:
            tag = "" if k == "FULL" else f"(前 {KEEP_UNTRACKED_LINES} 行)"
            note = ""
            skip = False
            if grp and p != grp[0]:
                rep_ln = news_cache.get(grp[0], ("", 0, ""))[1]
                if is_outlier(total_ln, rep_ln):
                    note = OUTLIER_NOTE
                else:
                    note = "  [相似组，内容略]"
                    skip = True
            print(f"\n## [新增] {p}  (共 {total_ln} 行{tag}){note}")
            if not skip:
                # 行数截断管长文件，字节帽管单行大文件，双保险缺一不可
                print(trunc_bytes(body))

    # 修改（相似组代表详列 diff，离群成员转为详列，其余略）
    print("\n=== 修改 ===")
    mods_sorted = sorted(mods, key=lambda x: x[0])
    mods_groups = find_similar_groups([e[0] for e in mods_sorted])
    printed_mods = set()
    mods_ln = {}  # 成员 diff 行数缓存；代表按字母序先遍历，离群判断时必已就位
    for entry in mods_sorted:
        p = entry[0]
        grp = maybe_group_banner(p, mods_groups, printed_mods)
        body, b = diff_for(p, cwd)
        if b:
            print(f"\n## [修改] {p}  (binary)")
            print("(binary, 内容跳过)")
            continue
        mods_ln[p] = len(body.splitlines())
        note = ""
        skip = False
        if grp and p != grp[0]:
            # 与新增组同判据：diff 行数与代表相差悬殊则详列，防止整组语义被代表掩盖
            if is_outlier(mods_ln[p], mods_ln.get(grp[0], -1)):
                note = OUTLIER_NOTE
            else:
                note = "  [相似组，diff 略]"
                skip = True
        print(f"\n## [修改] {p}{note}")
        if not skip:
            print(trunc_bytes(trunc_lines(body, LARGE_DIFF_LINES, KEEP_DIFF_LINES)))

    # 删除（相似组只加标记，成员本就仅文件名+行数）
    print("\n=== 删除 ===")
    dels_sorted = sorted(dels, key=lambda x: x[0])
    dels_groups = find_similar_groups([e[0] for e in dels_sorted])
    printed_dels = set()
    for entry in dels_sorted:
        p = entry[0]
        maybe_group_banner(p, dels_groups, printed_dels)
        lc = head_line_count(p, cwd)
        if lc >= 0:
            print(f"\n## [删除] {p}  (HEAD 中 {lc} 行)")
        else:
            print(f"\n## [删除] {p}")

    # 改名（组键取新路径；相似组代表详列 diff，离群成员转为详列，其余略）
    print("\n=== 改名 ===")
    rens_sorted = sorted(rens, key=lambda x: x[1])
    rens_groups = find_similar_groups([e[1] for e in rens_sorted])
    printed_rens = set()
    rens_ln = {}  # 成员 diff 行数缓存；代表按字母序先遍历，离群判断时必已就位
    for old, new in rens_sorted:
        grp = maybe_group_banner(new, rens_groups, printed_rens)
        body, b = diff_for(new, cwd)
        if b:
            print(f"\n## [改名] {old} -> {new}  (binary)")
            print("(binary, 内容跳过)")
            continue
        rens_ln[new] = len(body.splitlines())
        note = ""
        skip = False
        if grp and new != grp[0]:
            # 与新增/修改组同判据，三组文案统一为 OUTLIER_NOTE
            if is_outlier(rens_ln[new], rens_ln.get(grp[0], -1)):
                note = OUTLIER_NOTE
            else:
                note = "  [相似组，diff 略]"
                skip = True
        print(f"\n## [改名] {old} -> {new}{note}")
        if not skip:
            print(trunc_bytes(trunc_lines(body, LARGE_DIFF_LINES, KEEP_DIFF_LINES)))

    # 未解决合并冲突
    if unmerged:
        print("\n=== 合并冲突 ===")
        for p in unmerged:  # unmerged 已是去重排序后的纯路径列表
            print(f"\n## [冲突] {p}")
            print("(存在未解决的合并冲突标记，请先解决)")

    print("\n=== END ===")


if __name__ == "__main__":
    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    collect(cwd)
