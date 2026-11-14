---
name: commit-message-assistant
description: "Use when user asks for commit messages / 提交备注 / 帮我写提交信息 / 这些改动怎么写提交. Read-only: collects uncommitted changes via diff/ls-files, generates paste-ready Conventional Commits per file, auto-grouping batch-similar files, plus cross-file commit grouping suggestions. Commits only after the user's explicit approval, never pushes. Not for git Q&A or PR descriptions."
---

# Commit Message Assistant

## Goal
在用户提交前，为每个未提交的改动文件生成一条可直接粘贴的 Conventional Commits 单行 message + 一行功能级理由，供用户复制；同构批量文件（如脚本切出的多年份 JSON）聚合为一条，不逐份凑数；末尾再给出跨文件提交分组建议（哪些文件适合同一次 commit 及其合并 message）。采集全程只读；提交默认由用户手动完成，仅当用户明确审批（双要件，见 Workflow 第 9 步）时才代为 add + commit，永不 push。

## Workflow
1. 确认目标目录是 git 仓库；非仓库 → 告知"当前目录不是 git 仓库。"并停。
2. 定位技能根目录（即本 SKILL.md 所在目录），在其下运行 `scripts/collect_changes.py <目标仓库路径>`（只读），汇总全部未提交改动；目标仓库为当前工作目录时可省略参数，传仓库子目录时脚本自动以仓库根为基准采集。
3. 脚本输出 `NOT_A_REPO` / `NO_CHANGES` / 改动清单。若 `NO_CHANGES` → 告知"没有未提交改动，无需生成。"并停。
4. 读 `references/commit-conventions.md`（type 与 scope 规则）、`references/message-style-guide.md`（措辞、理由写法与提交建议格式）和 `examples/sample-output.md`（输出格式参照，防走样）。
5. 脚本已按类型分组（新增→修改→删除→改名→合并冲突）、组内字母序，并对同构批量文件输出 `SIMILAR_GROUP` 标记（组内仅代表文件详列内容，离群成员转详列，其余标注"内容略"）。默认逐文件生成：
   - 一行文件名（`### 相对路径`）：清晰标注本条 message 对应的文件
   - 一行 message：`type(scope): 主题`。单文件多变更 → type 取主导，主题短句带上次要改动。
   - 一行理由（斜体）：功能级描述"实现/增添了什么"，不进 commit。
   - `SIMILAR_GROUP` 标记的一组文件 → 聚合为一条：`### 目录/（N 个文件：清单）` + 一条 message（主题写批量操作+范围/数量）+ 一行理由，格式见 `message-style-guide.md`。
6. 清单末尾追加 `## 💡 提交建议` 一节：按"同 scope / 同目录 / 同一逻辑变更"把逐文件条目归为若干建议提交组，每组给组名、文件清单和一条合并后的 message（格式见 `message-style-guide.md`）；单文件不凑数，无分组价值则整节省略。
7. 输出清单供用户复制。若脚本提示 `WARN`（>50 文件或合并冲突）则保留顶部提醒。
8. 若用户要求"直接提交/推送"但**未给出审批语义与明确目标**：不执行任何写操作，重生清单并提醒用户手动提交。
9. **审批提交**（双要件缺一不可）：①明确审批语义——用户表示"已经仔细审批了，帮用户提交吧"或同等明确表述；②明确目标——点名文件路径、点名提交建议组编号（如"提交建议 1 和 3"）或说"全部"。两要件齐备 → 按建议组顺序逐组执行，每组：
   - `git add <点名路径>`：只 add 授权集内的显式路径，**严禁 `git add -A` / `git add .`**
   - 只读核对：`git diff --cached --name-status` 确认暂存集 == 授权集；不一致 → 停手报告差异，等用户裁决（reset 是写命令，不代执行）
   - `git commit -m "<该组合并 message>"`：一次一组；失败（如 pre-commit hook 拒绝）→ 原样转述 git 报错，停手不重试，**严禁 `--no-verify`**
   - 报告该组 commit hash（`git log -1 --oneline`）与剩余未提交文件；某组失败即停，后续组不执行

## Decision Tree
- 非仓库 / 无改动 → 提示并停。
- 改动 > 50 → 顶部加提醒，仍全列。
- 传仓库子目录 → 脚本自动定位仓库根，以根为基准采集，路径语义与仓库根调用一致。
- 单文件多变更 → type 取主导，主题带次要。
- `SIMILAR_GROUP`（≥3 个路径数字归一化后同模式的文件）→ 聚合一条 message：主题写批量操作+范围/数量（如"按年份切分数据为 2015–2024 共 10 份 JSON"）；标题行列目录+数量+清单；理由说明同构批量、适合合并为一次提交。脚本详列的代表文件与"离群，已详列"的成员（体量与代表相差悬殊，新增按行数、修改/改名按 diff 行数）用于把握整批语义。
- 二进制文件 → 脚本已跳内容仅留文件名+类型；message 据类型与文件名给。
- untracked 大文件 → 脚本已读前 80 行+总行数；行数阈值内的单行超大文件（压缩 JSON/minified JS）由 16KB 字节帽兜底截断。
- 删除文件 → 脚本只输出文件名与 HEAD 中行数，不输出 diff；message 据文件名与路径推断用途。
- 合并冲突 → 脚本用 `ls-files --unmerged` 权威枚举（`git diff HEAD` 会把冲突文件伪装成普通修改），在"合并冲突"分组中列出；提示用户先解决冲突再生成 commit message。
- 全新仓库（无 HEAD）→ 脚本自动用 `git diff --cached` 取 staged 文件，untracked 正常取。
- scope 可靠推断则带，否则省略。
- 提交建议：同一逻辑变更落在多个文件（如 feature + 其调用点）→ 建议合并为一次提交并给合并 message；相互独立、跨模块的文件不硬凑组。
- 审批提交（双要件齐备）→ 按 Workflow 第 9 步逐组 add + commit；push / tag / amend / force 永久禁止。只说"提交吧"而无审批语义或无明确目标 → 按第 8 步处理，不猜目标。
- 被要求 push / 打 tag / amend → 拒绝并提醒用户手动执行。

## Constraints
- **只读为默认**：采集阶段仅允许 `git status` / `git diff` / `git diff --name-status` / `git diff --cached` / `git log` / `git show` / `git ls-files` / `git rev-parse` 及 `collect_changes.py`，严禁 `push` / `merge` / `rebase` / `reset` / `checkout` / `stash` / `tag` / `amend` 等任何改变仓库状态的命令。
- **提交唯一豁免**（双要件缺一不可，见 Workflow 第 9 步）：用户明确审批 + 明确点名目标后，才允许 `git add <显式路径>` 与 `git commit -m`。豁免范围内也**永久禁止** `git add -A` / `git add .` / `git commit --no-verify` / `--amend` / `git push` / `git tag`。
- 默认提交动作由用户手动完成，技能只产文本；审批协议未满足时一律回退到产文本模式。
- message 单行；理由独立一行且不粘贴。
- type 英文、正文中文；用户一句话可切英文/自由格式。
- scope 仅目录结构能可靠推断时给出，否则省略，不强凑。
- 提交建议仅供参考，不替用户决定提交切分；无分组价值时省略该节。

## Validation
- frontmatter `name`/`description` 存在且合法；`name` 为 lowercase-hyphen-case。
- `scripts/collect_changes.py`、`references/commit-conventions.md`、`references/message-style-guide.md` 均存在。
- 真实路径可走通：有改动仓库 → 跑脚本 → 出逐文件清单 + 提交建议，全程无写操作。
- 脚本无 add/commit/push 调用（grep 确认）。
- 审批提交走查：未满足双要件时零写操作；满足时暂存集与授权集核对一致、逐组 commit 成功且有 hash 报告。
- `tests/selftest.sh` 全绿：临时仓库覆盖新增/修改/删除/改名/二进制/全新仓库/相似组（聚合与不聚合双向断言）/修改组离群/单行超大文件字节帽/子目录根定位/合并冲突（ls-files --unmerged 权威判定），并断言脚本运行前后 HEAD 不变（只读性）。

## Resources
- `scripts/collect_changes.py`：只读采集改动（name-status + 各文件 diff/新文件内容，行数截断与 16KB 字节帽双保险、二进制处理）。每次生成都跑。支持全新仓库（无 HEAD 时自动 fallback 到 `--cached`）、合并冲突检测（`ls-files --unmerged` 权威枚举，绕开 `diff HEAD` 把冲突伪装成修改的盲区）、子目录调用自动定位仓库根、相似组检测（路径数字归一化，≥3 个同模式文件打 `SIMILAR_GROUP` 标记，组内代表详列、其余略、新增/修改/改名三组对称支持离群成员转详列）。
- `references/commit-conventions.md`：Conventional Commits type 列表、scope 规则、速查。
- `references/message-style-guide.md`：单行 message 措辞、多变更折叠、相似组聚合、理由写法、提交建议格式、从建议到提交的审批协议、好坏对照。
- `examples/sample-output.md`：五种典型场景的脚本输出与技能最终结果对照，作输出格式参照。
