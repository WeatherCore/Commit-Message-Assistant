# Conventional Commits 速查（commit-message-assistant）

本技能默认采用 Conventional Commits：type 英文、subject 中文。

## 格式
```
type(scope): subject
```
- 单行。scope 可选。
- type 英文小写；subject 中文短句，描述"做了什么"。
- 不把 body 写进 message——多变更细节放 subject 短句，功能级说明放独立的"理由"行（见 `message-style-guide.md`）。

## type 列表
| type | 用途 | 典型触发 |
|------|------|----------|
| feat | 新功能 | 新增邮箱登录接口 |
| fix | 修 bug | 修复登录空指针 |
| docs | 文档 | 更新 README |
| style | 格式（不改逻辑） | 调整缩进 / 换行 |
| refactor | 重构（非 feat/fix） | 抽取重复逻辑为函数 |
| perf | 性能 | 缓存查询结果 |
| test | 测试 | 补充单测 |
| build | 构建系统 / 依赖 | 升级 webpack |
| ci | CI 配置 | 改 GitHub Actions |
| chore | 杂务（非 src/test） | 改 .gitignore |
| revert | 回滚 | 撤销某次提交 |

## scope 规则
- 仅当能从目录结构**可靠**推断时才带 scope。
- 例：`src/auth/login.js` → `scope=auth`；`packages/server/...` → `scope=server`。
- 拿不准、范围模糊、单文件跨多模块 → **省略** scope，不强凑。
- scope 小写，单词或短横线连接。

## type 选择优先级
单文件多变更时，按"主导变更"选 type：
- 同时有 feat 与 refactor：主导是 feat → `feat`，subject 短句带上 refactor。
- 修 bug 顺手重构：主导 fix → `fix`，subject 带上"顺手重构 X"。
- 主导判断：这次改这一文件，用户最想表达的是"加了功能"还是"修了 bug"还是"重构"。

## 切换规范
- 用户一句"用英文" → type 与 subject 都用英文。
- 用户一句"自由格式" → 不加 type 前缀，直接中文短句描述。
- 默认不切换。
