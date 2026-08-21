# Description

## 中文版

COMMA 帮你在每次提交前为每个未提交改动文件生成可粘贴的 Conventional Commits 单行信息与一行功能级理由。其含金量在只读采集与工程约束：collect_changes.py 以 git diff HEAD --name-status -z（NUL 分隔）取净变更，新文件按 300 行、diff 按 200 行截断，二进制按 null 字节检测跳内容留文件名；全程仅调 rev-parse/diff/ls-files，严禁 add/commit/push，提交完全由用户手动。工程由 SKILL.md 加一脚本加两份 references 规范构成，渐进式披露。适合逐文件写规范提交信息且忌误触仓库的开发者。

## English

ZCode skill producing paste-ready Conventional Commits messages—one line plus rationale per file. Read-only by design: collect_changes.py truncates at 300/200 lines, skips binaries by null-byte check, and never calls add/commit/push—only rev-parse/diff/ls-files. SKILL.md, one script, two references. For devs wanting per-file conventional messages.
