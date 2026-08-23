# Description

## 中文版

Commit Message Assistant 是一个提交前为每个改动文件生成可粘贴 Conventional Commits 提交信息的只读技能，绝不代为提交或推送。其含金量在采集鲁棒性与安全承诺：git 调用严格只读，-z 解析加 -M 重命名检测覆盖新增、修改、删除、改名、冲突五类改动，大 diff 与新文件自动截断、二进制跳过以保护上下文，同构批量文件（如年份切割的多年份 JSON）经路径数字归一化聚成相似组、聚合为一条 message 而非逐份凑数，无 HEAD 的全新仓库自动回退 staged 采集，Windows 下强制 UTF-8 防乱码。由 collect_changes.py 与规范文档构成，适合日常提交前快速产出规范提交信息。

## English

Commit Message Assistant generates paste-ready Conventional Commits messages per changed file before you commit — fully read-only, never runs add/commit/push. Its value lies in safe, robust collection: strict git read-only, -z parsing with -M rename detection covering add/modify/delete/rename/conflict, auto-truncation of large diffs and binary skip to protect context, similar-file grouping that collapses batch-generated files (e.g. year-split JSONs) into one message instead of per-file noise, fallback to --cached on fresh repos without HEAD, and forced UTF-8 on Windows. A single Python collector plus spec docs, ideal for daily commit hygiene.

