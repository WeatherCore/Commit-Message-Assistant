---
name: commit-message-assistant
description: "Use when user asks for commit messages / 提交备注 / 帮我写提交信息 / 这些改动怎么写提交. Read-only: collects uncommitted changes via diff/ls-files, generates paste-ready Conventional Commits per file, auto-grouping batch-similar files. Never commits or pushes. Not for git Q&A or PR descriptions."
---

# Commit Message Assistant

## Goal
在用户提交前，为每个未提交的改动文件生成一条可直接粘贴的 Conventional Commits 单行 message + 一行功能级理由，供用户复制；同构批量文件（如脚本切出的多年份 JSON）聚合为一条，不逐份凑数。全程只读，绝不代为提交或推送。

## Workflow
1. 确认目标目录是 git 仓库；非仓库 → 告知"当前目录不是 git 仓库。"并停。
2. 定位技能根目录（即本 SKILL.md 所在目录），在其下运行 `scripts/collect_changes.py <目标仓库路径>`（只读），汇总全部未提交改动；目标仓库为当前工作目录时可省略参数。
3. 脚本输出 `NOT_A_REPO` / `NO_CHANGES` / 改动清单。若 `NO_CHANGES` → 告知"没有未提交改动，无需生成。"并停。
4. 读 `references/commit-conventions.md`（type 与 scope 规则）、`references/message-style-guide.md`（措辞与理由写法）和 `examples/sample-output.md`（输出格式参照，防走样）。
5. 脚本已按类型分组（新增→修改→删除→改名）、组内字母序，并对同构批量文件输出 `SIMILAR_GROUP` 标记（组内仅代表文件详列内容，其余标注"内容略"）。默认逐文件生成：
   - 一行文件名（`### 相对路径`）：清晰标注本条 message 对应的文件
   - 一行 message：`type(scope): 主题`。单文件多变更 → type 取主导，主题短句带上次要改动。
   - 一行理由（斜体）：功能级描述"实现/增添了什么"，不进 commit。
   - `SIMILAR_GROUP` 标记的一组文件 → 聚合为一条：`### 目录/（N 个文件：清单）` + 一条 message（主题写批量操作+范围/数量）+ 一行理由，格式见 `message-style-guide.md`。
6. 输出清单供用户复制。若脚本提示 `WARN`（>50 文件或合并冲突）则保留顶部提醒。
7. 若用户要求"直接提交/推送"：不执行任何写操作，重生清单并提醒用户手动提交。

## Decision Tree
- 非仓库 / 无改动 → 提示并停。
- 改动 > 50 → 顶部加提醒，仍全列。
- 单文件多变更 → type 取主导，主题带次要。
- `SIMILAR_GROUP`（≥3 个路径数字归一化后同模式的文件）→ 聚合一条 message：主题写批量操作+范围/数量（如"按年份切分数据为 2015–2024 共 10 份 JSON"）；标题行列目录+数量+清单；理由说明同构批量、适合合并为一次提交。脚本详列的代表文件与"行数离群，已详列"的成员用于把握整批语义。
- 二进制文件 → 脚本已跳内容仅留文件名+类型；message 据类型与文件名给。
- untracked 大文件 → 脚本已读前 80 行+总行数，据此写理由。
- 删除文件 → 脚本只输出文件名与 HEAD 中行数，不输出 diff；message 据文件名与路径推断用途。
- 合并冲突（U 标记）→ 脚本在"合并冲突"分组中列出；提示用户先解决冲突再生成 commit message。
- 全新仓库（无 HEAD）→ 脚本自动用 `git diff --cached` 取 staged 文件，untracked 正常取。
- scope 可靠推断则带，否则省略。
- 被要求提交/推送 → 拒绝写操作，重生清单+提醒。

## Constraints
- **只读**：仅允许 `git status` / `git diff` / `git diff --name-status` / `git diff --cached` / `git log` / `git show` / `git ls-files` / `git rev-parse` 及 `collect_changes.py`。严禁 `git add` / `commit` / `push` / `merge` / `rebase` / `reset` / `checkout` / `stash` 等任何改变仓库状态的命令。
- 仓库提交动作全部由用户手动完成，技能只产文本。
- message 单行；理由独立一行且不粘贴。
- type 英文、正文中文；用户一句话可切英文/自由格式。
- scope 仅目录结构能可靠推断时给出，否则省略，不强凑。

## Validation
- frontmatter `name`/`description` 存在且合法；`name` 为 lowercase-hyphen-case。
- `scripts/collect_changes.py`、`references/commit-conventions.md`、`references/message-style-guide.md` 均存在。
- 真实路径可走通：有改动仓库 → 跑脚本 → 出逐文件清单，全程无写操作。
- 脚本无 add/commit/push 调用（grep 确认）。
- `tests/selftest.sh` 全绿：临时仓库覆盖新增/修改/删除/改名/二进制/全新仓库/相似组（聚合与不聚合双向断言），并断言脚本运行前后 HEAD 不变（只读性）。

## Resources
- `scripts/collect_changes.py`：只读采集改动（name-status + 各文件 diff/新文件内容，截断与二进制处理）。每次生成都跑。支持全新仓库（无 HEAD 时自动 fallback 到 `--cached`）、合并冲突检测与相似组检测（路径数字归一化，≥3 个同模式文件打 `SIMILAR_GROUP` 标记，组内代表详列、其余略、新增组行数离群者详列）。
- `references/commit-conventions.md`：Conventional Commits type 列表、scope 规则、速查。
- `references/message-style-guide.md`：单行 message 措辞、多变更折叠、相似组聚合、理由写法、好坏对照。
- `examples/sample-output.md`：四种典型场景的脚本输出与技能最终结果对照，作输出格式参照。
