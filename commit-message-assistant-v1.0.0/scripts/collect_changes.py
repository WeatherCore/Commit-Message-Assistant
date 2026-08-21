#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读采集 git 未提交改动，为 commit-message-assistant 提供生成素材。

安全约束：仅调用只读 git 子命令（rev-parse / diff / ls-files）和读取文件，
绝不执行 add/commit/push 等任何改变仓库状态的命令。
"""
import os
import sys
import subprocess

# 截断 / 阈值参数
LARGE_DIFF_LINES = 200      # tracked 文件 diff 超过此行数则截断
KEEP_DIFF_LINES = 80        # 截断后保留的前 N 行
UNTRACKED_FULL_LINES = 300  # 新文件行数 <= 此值则读全文
KEEP_UNTRACKED_LINES = 80   # 新文件截断后保留的前 N 行
MANY_FILES = 50            # 改动文件超过此数则加提醒


def git(args, cwd):
    p = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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


def diff_for(path, cwd):
    """返回 (body, is_binary)。body 为 git diff 文本或空串。"""
    rc, out, _ = git(["diff", "HEAD", "--", path], cwd)
    if rc != 0:
        return "", False
    if "Binary files" in out or "GIT binary patch" in out:
        return "", True
    return out, False


def read_newfile(path, cwd):
    """读新文件（staged-A 或 untracked）内容。返回 (body, total_lines, kind)。
    kind ∈ {FULL, TRUNC, BINARY, ERROR}。
    """
    full = os.path.join(cwd, path)
    try:
        with open(full, "rb") as f:
            raw = f.read()
    except Exception as e:
        return str(e), 0, "ERROR"
    if is_binary(raw):
        return "", 0, "BINARY"
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

    # tracked 改动（相对 HEAD 的净变更）
    tracked = []
    rc, out, _ = git(["diff", "HEAD", "--name-status", "-z"], cwd)
    if rc == 0:
        tracked = parse_name_status(out)
    # rc != 0：尚无 HEAD（全新仓库），tracked 为空，全部走新文件

    rc2, out2, _ = git(["ls-files", "--others", "--exclude-standard", "-z"], cwd)
    untracked = [p for p in out2.split("\0") if p] if rc2 == 0 else []

    news, mods, dels, rens = [], [], [], []
    for letter, p1, p2 in tracked:
        if letter == "A":
            news.append(("staged", p1))
        elif letter == "D":
            dels.append(("staged", p1))
        elif letter in ("R", "C"):
            rens.append((p1, p2 or p1))
        else:  # M 及 T/X 等少见，归入修改
            mods.append(("staged", p1))
    for p in untracked:
        news.append(("untracked", p))

    total = len(news) + len(mods) + len(dels) + len(rens)
    print(f"REPO: {os.path.abspath(cwd)}")
    print(f"TOTAL: {total}")
    if total == 0:
        print("NO_CHANGES")
        return
    if total > MANY_FILES:
        print(f"WARN: 改动较多({total} 个)，请逐条核对")

    # 新增
    print("\n=== 新增 ===")
    for kind, p in sorted(news, key=lambda x: x[1]):
        body, total_ln, k = read_newfile(p, cwd)
        if k == "BINARY":
            print(f"\n## [新增] {p}  ({kind}, binary)")
            print("(binary, 内容跳过)")
        elif k == "ERROR":
            print(f"\n## [新增] {p}  ({kind}, 读取失败)")
            print(body)
        else:
            tag = "" if k == "FULL" else f"(前 {KEEP_UNTRACKED_LINES})"
            print(f"\n## [新增] {p}  ({kind}, 共 {total_ln} 行{tag})")
            print(body)

    # 修改
    print("\n=== 修改 ===")
    for kind, p in sorted(mods, key=lambda x: x[1]):
        body, b = diff_for(p, cwd)
        if b:
            print(f"\n## [修改] {p}  (binary)")
            print("(binary, 内容跳过)")
        else:
            print(f"\n## [修改] {p}")
            print(trunc_lines(body, LARGE_DIFF_LINES, KEEP_DIFF_LINES))

    # 删除
    print("\n=== 删除 ===")
    for kind, p in sorted(dels, key=lambda x: x[1]):
        body, b = diff_for(p, cwd)
        if b:
            print(f"\n## [删除] {p}  (binary)")
            print("(binary, 内容跳过)")
        else:
            print(f"\n## [删除] {p}")
            print(trunc_lines(body, LARGE_DIFF_LINES, KEEP_DIFF_LINES))

    # 改名
    print("\n=== 改名 ===")
    for old, new in sorted(rens, key=lambda x: x[1]):
        body, b = diff_for(new, cwd)
        if b:
            print(f"\n## [改名] {old} -> {new}  (binary)")
            print("(binary, 内容跳过)")
        else:
            print(f"\n## [改名] {old} -> {new}")
            print(trunc_lines(body, LARGE_DIFF_LINES, KEEP_DIFF_LINES))

    print("\n=== END ===")


if __name__ == "__main__":
    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    collect(cwd)
