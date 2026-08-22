#!/usr/bin/env bash
# collect_changes.py 自检脚本：在临时 git 仓库构造各类改动，断言脚本输出关键内容，
# 并验证只读性（脚本运行前后仓库状态一致）。
# 用法: bash tests/selftest.sh   （需要 bash + git + python3/python，可用 PYTHON 环境变量指定解释器）
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/scripts/collect_changes.py"

# 定位 python（可用 PYTHON 环境变量覆盖）
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON=python
  else
    echo "FAIL: 找不到 python3/python，请设置 PYTHON 环境变量"
    exit 1
  fi
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

# --- 只读性断言：脚本运行前后 git 状态必须一致 ---
if diff -q "$TMP/status_before1.txt" "$TMP/status_after1.txt" > /dev/null 2>&1; then
  echo "PASS: 只读性（运行前后 git status 一致）"
  PASSED=$((PASSED + 1))
else
  echo "FAIL: 只读性（脚本运行改变了仓库状态！）"
  diff "$TMP/status_before1.txt" "$TMP/status_after1.txt"
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
