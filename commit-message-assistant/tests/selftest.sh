#!/usr/bin/env bash
# collect_changes.py 自检脚本：在临时 git 仓库构造各类改动，断言脚本输出关键内容，
# 并验证只读性（脚本运行前后仓库状态一致）。
# 用法: bash tests/selftest.sh   （需要 bash + git + python3/python，可用 PYTHON 环境变量指定解释器）
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/collect_changes.py"

# 定位 python（可用 PYTHON 环境变量覆盖）；逐个验证能真正执行代码，
# 跳过 WindowsApps 的 python3 存根（command -v 找得到，运行却失败）
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  for cand in python3 python; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c pass >/dev/null 2>&1; then
      PYTHON="$cand"
      break
    fi
  done
fi
if [ -z "$PYTHON" ]; then
  echo "FAIL: 找不到可运行的 python3/python，请设置 PYTHON 环境变量"
  exit 1
fi

TMP="$(mktemp -d)"
# Git Bash / MSYS 下 mktemp -d 可能返回 Windows 风格路径（C:\...\Temp\xxx），
# 统一转成 POSIX 路径，避免 bash 重定向与 grep/diff 读取时路径解析不一致。
if command -v cygpath >/dev/null 2>&1; then
  TMP="$(cygpath -u "$TMP")"
fi
trap 'cd / 2>/dev/null; rm -rf "$TMP"' EXIT
FAILED=0
PASSED=0

# Windows 原生 python.exe 不识别 /d/... 风格的 MSYS 路径，传参前转成 Windows 风格。
# Linux/macOS 无 cygpath，保持原路径。
if command -v cygpath >/dev/null 2>&1; then
  SCRIPT_ARG="$(cygpath -w "$SCRIPT")"
else
  SCRIPT_ARG="$SCRIPT"
fi
run_py() { # 统一入口：强制 UTF-8 输出 + 可识别路径
  PYTHONIOENCODING=utf-8 "$PYTHON" "$SCRIPT_ARG" "$@"
}

check() { # $1=描述  $2=要匹配的模式  $3=输出文件
  if grep -q -- "$2" "$3"; then
    echo "PASS: $1"
    PASSED=$((PASSED + 1))
  else
    echo "FAIL: $1  (输出中未找到: $2)"
    FAILED=$((FAILED + 1))
  fi
}

check_not() { # $1=描述  $2=不应出现的模式  $3=输出文件
  if grep -q -- "$2" "$3"; then
    echo "FAIL: $1  (输出中不应出现: $2)"
    FAILED=$((FAILED + 1))
  else
    echo "PASS: $1"
    PASSED=$((PASSED + 1))
  fi
}

# --- 场景 1：常规仓库（修改 / untracked 新增 / 删除 / staged 二进制新增） ---
R1="$TMP/r1"
mkdir -p "$R1" && cd "$R1" || exit 1
git init -q .
printf 'hello\n' > a.txt
git add a.txt && git -c user.name=t -c user.email=t@t commit -qm init
printf 'world\n' >> a.txt                                        # 修改（unstaged）
printf 'def f():\n    return 1\n' > b.py                         # untracked 新增
printf 'old\n' > c.txt && git add c.txt && git -c user.name=t -c user.email=t@t commit -qm 'add c'
rm -f c.txt 2>/dev/null || true   # 沙箱/回收站拦截 rm 时兜底（git rm 更可靠，见下）
git rm -q c.txt                    # staged 删除，绕开 shell 删除拦截
printf '\x00\x01\x02binary' > e.bin && git add -A                # staged 二进制新增
git status --porcelain > "$TMP/status_before1.txt"
run_py . > "$TMP/out1.txt" 2>&1
git status --porcelain > "$TMP/status_after1.txt"

check "场景1 修改 diff"              '## \[修改\] a\.txt'            "$TMP/out1.txt"
check "场景1 untracked 新增"        '## \[新增\] b\.py'             "$TMP/out1.txt"
check "场景1 二进制跳过内容"         '## \[新增\] e\.bin  (binary)'  "$TMP/out1.txt"
check "场景1 删除+HEAD行数"          '## \[删除\] c\.txt  (HEAD 中 1 行)' "$TMP/out1.txt"

# --- 场景 2：全新仓库（无 HEAD，fallback 到 --cached） ---
R2="$TMP/r2"
mkdir -p "$R2" && cd "$R2" || exit 1
git init -q .
printf 'x\n' > f1.py && git add f1.py
run_py . > "$TMP/out2.txt" 2>&1
check "场景2 全新仓库 fallback"      '## \[新增\] f1\.py'            "$TMP/out2.txt"

# --- 场景 3：改名（脚本带 -M，不依赖全局 diff.renames 配置） ---
git -c user.name=t -c user.email=t@t commit -qm init
git mv f1.py f2.py
run_py . > "$TMP/out3.txt" 2>&1
check "场景3 改名分组"               '## \[改名\] f1\.py -> f2\.py' "$TMP/out3.txt"

# --- 场景 4：相似组（≥3 个同模式文件聚合标记；2 个不触发；新增/修改组离群详列）---
#              + 字节帽（单行超大文件）。
# data/*.json 为 untracked 新增组；cfg/v*.py 先提交再改动，构成 tracked 修改组；
# big/oneline.json 为单行 >16KB 文件，验证行数截断防不住的字节帽。
R4="$TMP/r4"
mkdir -p "$R4/data" "$R4/misc" "$R4/cfg" "$R4/big" && cd "$R4" || exit 1
git init -q .
git -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
for y in 2015 2016 2017; do printf '{"year": %s}\n' "$y" > "data/$y.json"; done
{ echo '{'; for i in 1 2 3 4 5 6 7 8; do echo "  \"row_$i\": $i,"; done; \
  echo '"year": 2018'; echo '}'; } > data/2018.json               # 12 行，与代表相差悬殊
printf 'x1\n' > misc/x1.txt
printf 'x2\n' > misc/x2.txt
for v in 1 2 3; do printf 'x = %s\n' "$v" > "cfg/v$v.py"; done
git add cfg && git -c user.name=t -c user.email=t@t commit -qm 'cfg base'  # 仅提交 cfg，data/misc 保持 untracked
printf '# tweak 1\n' >> cfg/v1.py                                 # 小 diff（代表）
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 \
         21 22 23 24 25 26 27 28 29 30; do printf '# pad %s\n' "$i" >> cfg/v2.py; done
printf '# tweak 3\n' >> cfg/v3.py                                 # 小 diff（非离群）
printf '{"blob":"%s"}\n' "$(head -c 20000 /dev/zero | tr '\0' 'a')" > big/oneline.json  # 单行 ~20KB
git status --porcelain > "$TMP/status_before4.txt"
run_py . > "$TMP/out4.txt" 2>&1
git status --porcelain > "$TMP/status_after4.txt"

check     "场景4 相似组标记"          '>> SIMILAR_GROUP: data/#\.json ×4'                     "$TMP/out4.txt"
check     "场景4 代表详列"            '## \[新增\] data/2015\.json  (共 1 行)'                 "$TMP/out4.txt"
check     "场景4 成员内容略"          '## \[新增\] data/2016\.json  (共 1 行)  \[相似组，内容略\]' "$TMP/out4.txt"
check     "场景4 离群成员详列"        '\[相似组，离群，已详列\]'                                "$TMP/out4.txt"
check_not "场景4 两个文件不聚合"      '>> SIMILAR_GROUP: misc'                                  "$TMP/out4.txt"
check     "场景4 修改组相似标记"      '>> SIMILAR_GROUP: cfg/v#\.py ×3'                        "$TMP/out4.txt"
check     "场景4 修改组离群详列"      '## \[修改\] cfg/v2\.py  \[相似组，离群，已详列\]'        "$TMP/out4.txt"
check     "场景4 修改组非离群略"      '## \[修改\] cfg/v3\.py  \[相似组，diff 略\]'             "$TMP/out4.txt"
check     "场景4 单行大文件字节帽"    '超 16KB 已截断'                                          "$TMP/out4.txt"

# --- 场景 5：子目录调用（自动定位仓库根，路径以根为基准） ---
run_py data > "$TMP/out5.txt" 2>&1
check "场景5 REPO 指向仓库根"        'REPO:.*r4'                     "$TMP/out5.txt"
check "场景5 路径根相对"             '## \[新增\] data/2015\.json'   "$TMP/out5.txt"

# --- 场景 6：合并冲突（U 状态检测与提醒） ---
R6="$TMP/r6"
mkdir -p "$R6" && cd "$R6" || exit 1
git init -q .
printf 'base\n' > conflict.txt
git add conflict.txt && git -c user.name=t -c user.email=t@t commit -qm base
BASE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git checkout -qb feature
printf 'feature line\n' >> conflict.txt
git -c user.name=t -c user.email=t@t commit -qam feature
git checkout -q "$BASE_BRANCH"
printf 'main line\n' >> conflict.txt
git -c user.name=t -c user.email=t@t commit -qam main
git merge feature >/dev/null 2>&1 || true                          # 制造未解决冲突
run_py . > "$TMP/out6.txt" 2>&1

check "场景6 冲突分组"               '=== 合并冲突 ==='                        "$TMP/out6.txt"
check "场景6 冲突文件标记"           '## \[冲突\] conflict\.txt'               "$TMP/out6.txt"
check "场景6 WARN 提醒"              'WARN: 1 个文件存在未解决的合并冲突'        "$TMP/out6.txt"

# --- 只读性断言：脚本运行前后 git 状态必须一致 ---
if diff -q "$TMP/status_before1.txt" "$TMP/status_after1.txt" > /dev/null 2>&1; then
  echo "PASS: 只读性（场景1 运行前后 git status 一致）"
  PASSED=$((PASSED + 1))
else
  echo "FAIL: 只读性（场景1 脚本运行改变了仓库状态！）"
  diff "$TMP/status_before1.txt" "$TMP/status_after1.txt"
  FAILED=$((FAILED + 1))
fi
if diff -q "$TMP/status_before4.txt" "$TMP/status_after4.txt" > /dev/null 2>&1; then
  echo "PASS: 只读性（场景4 运行前后 git status 一致）"
  PASSED=$((PASSED + 1))
else
  echo "FAIL: 只读性（场景4 脚本运行改变了仓库状态！）"
  diff "$TMP/status_before4.txt" "$TMP/status_after4.txt"
  FAILED=$((FAILED + 1))
fi

echo "----"
echo "通过 $PASSED / $((PASSED + FAILED))"
if [ "$FAILED" -eq 0 ]; then
  echo "SELFTEST OK"
else
  echo "SELFTEST FAILED"
  exit 1
fi
