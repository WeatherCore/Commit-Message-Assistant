---
name: commit-message-assistant
description: "Use when the user is about to commit to a git repo and asks for commit messages / 提交备注 / 帮我写提交信息 / 这些改动怎么写提交. Generates paste-ready Conventional Commits messages: reads uncommitted changes with read-only git (status/diff/ls-files, never add/commit/push), labels each file 新增/修改/删除/改名, and outputs one single-line message plus one function-level rationale per file. Never commits or pushes — if asked to commit/push, regenerate the text list and remind the user to do it manually. Not for git Q&A or PR descriptions."
---

# Commit Message Assistant

## Goal
在用户提交前，为每个未提交的改动文件生成一条可直接粘贴的 Conventional Commits 单行 message + 一行功能级理由，供用户复制。全程只读，绝不代为提交或推送。

## Workflow
1. 确认目标目录是 git 仓库；非仓库 → 告知"当前目录不是 git 仓库。"并停。
2. 在目标仓库目录下运行 `scripts/collect_changes.py`（技能目录下，只读），汇总全部未提交改动。
3. 脚本输出 `NOT_A_REPO` / `NO_CHANGES` / 改动清单。若 `NO_CHANGES` → 告知"没有未提交改动，无需生成。"并停。
4. 读 `references/commit-conventions.md`（type 与 scope 规则）和 `references/message-style-guide.md`（措辞与理由写法）。
5. 脚本已按类型分组（新增→修改→删除→改名）、组内字母序。逐文件生成：
   - 一行 message：`type(scope): 主题`。单文件多变更 → type 取主导，主题短句带上次要改动。
   - 一行理由（斜体）：功能级描述"实现/增添了什么"，不进 commit。
6. 输出清单供用户复制。若脚本提示 `WARN`（>50 文件）则保留顶部提醒。
7. 若用户要求"直接提交/推送"：不执行任何写操作，重生清单并提醒用户手动提交。

## Decision Tree
- 非仓库 / 无改动 → 提示并停。
- 改动 > 50 → 顶部加提醒，仍全列。
- 单文件多变更 → type 取主导，主题带次要。
- 二进制文件 → 脚本已跳内容仅留文件名+类型；message 据类型与文件名给。
- untracked 大文件 → 脚本已读前 80 行+总行数，据此写理由。
- scope 可靠推断则带，否则省略。
- 被要求提交/推送 → 拒绝写操作，重生清单+提醒。

## Constraints
- **只读**：仅允许 `git status` / `git diff` / `git diff --name-status` / `git log` / `git show` / `git ls-files` / `git rev-parse` 及 `collect_changes.py`。严禁 `git add` / `commit` / `push` / `merge` / `rebase` / `reset` / `checkout` / `stash` 等任何改变仓库状态的命令。
- 仓库提交动作全部由用户手动完成，技能只产文本。
- message 单行；理由独立一行且不粘贴。
- type 英文、正文中文；用户一句话可切英文/自由格式。
- scope 仅目录结构能可靠推断时给出，否则省略，不强凑。

## Validation
- frontmatter `name`/`description` 存在且合法；`name` 为 lowercase-hyphen-case。
- `scripts/collect_changes.py`、`references/commit-conventions.md`、`references/message-style-guide.md` 均存在。
- 真实路径可走通：有改动仓库 → 跑脚本 → 出逐文件清单，全程无写操作。
- 脚本无 add/commit/push 调用（grep 确认）。

## Resources
- `scripts/collect_changes.py`：只读采集改动（name-status + 各文件 diff/新文件内容，截断与二进制处理）。每次生成都跑。
- `references/commit-conventions.md`：Conventional Commits type 列表、scope 规则、速查。
- `references/message-style-guide.md`：单行 message 措辞、多变更折叠、理由写法、好坏对照。
