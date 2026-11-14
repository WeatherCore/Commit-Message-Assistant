# Description

## 中文版

Commit Message Assistant 是一个提交前为每个改动文件生成可粘贴 Conventional Commits 提交信息、并附跨文件提交分组建议的只读技能，默认不代提交，仅在用户明确审批后按建议组逐代为 add + commit，永不推送。含金量在采集鲁棒性与安全承诺：git 严格只读白名单，-z 加 -M 覆盖五类改动；行数截断外加 16KB 字节帽防单行大文件撑爆上下文；同构批量文件按路径数字归一化聚合为一条 message，三组对称支持离群成员转详列；冲突用 ls-files --unmerged 权威枚举；无 HEAD 自动回退 staged，传子目录自动定位仓库根；审批提交逐组核对暂存集，失败即停。适合日常提交前快速产出规范提交信息。

## English

Commit Message Assistant generates paste-ready Conventional Commits messages per changed file — plus cross-file commit-grouping suggestions — read-only by default, committing on your behalf only after explicit approval, and never pushing. Its value lies in robust, safe collection: strict read-only git whitelist, -z parsing with -M rename detection covering add/modify/delete/rename/conflict; a 16KB byte cap on top of line truncation so single-line minified blobs cannot blow the context; similar-file grouping via path digit normalization that collapses batch-generated files into one message, with outlier members surfaced in add/modify/rename groups; authoritative conflict detection via ls-files --unmerged; fallback to --cached on fresh repos without HEAD; automatic repo-root resolution when a subdirectory is passed; approval-gated commits verify the staged set per group and stop on first failure. A single Python collector plus spec docs, ideal for daily commit hygiene.
