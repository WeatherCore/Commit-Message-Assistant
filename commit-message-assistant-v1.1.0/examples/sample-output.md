# 示例输出

以下展示在四种典型场景下，`collect_changes.py` 的采集结果和技能最终生成的 commit message。

---

## 场景 1：修改 + 新增 + 删除

假设仓库 `my-project` 有以下未提交改动：
- 新增 `src/auth/email_login.py`（42 行）
- 修改 `src/auth/login_service.py`（+12 -3）
- 删除 `src/utils/legacy_config.js`（HEAD 中 87 行）

### collect_changes.py 输出

```
REPO: /home/user/my-project
TOTAL: 3

=== 新增 ===

## [新增] src/auth/email_login.py  (共 42 行)
import re
from .login_service import LoginService

def validate_email(email: str) -> bool:
    ...

=== 修改 ===

## [修改] src/auth/login_service.py
@@ -18,6 +18,15 @@ class LoginService:
+    def email_error_msg(self, code):
+        if code == "NOT_FOUND":
+            return "账号不存在"
 ...

=== 删除 ===

## [删除] src/utils/legacy_config.js  (HEAD 中 87 行)

=== END ===
```

### 技能生成结果

```
### src/auth/email_login.py
feat(auth): 新增邮箱登录校验
*理由：新增邮箱格式校验与查重逻辑，供 /login/email 接口使用。*

### src/auth/login_service.py
fix(auth): 细化登录失败错误码
*理由：把登录失败的错误信息从单一提示拆成"账号不存在/密码错/已锁定"三种，前端可据此做针对性提示；改了 LoginService.errorMsg 与 3 个调用点。*

### src/utils/legacy_config.js
chore: 移除废弃的 legacy_config.js
*理由：legacy_config.js 的配置已迁到 config/default.js，此文件无人引用，删除以减少歧义。*
```

---

## 场景 2：全新仓库（无 HEAD）

假设刚 `git init` 并 `git add` 了两个文件，还没有任何 commit。

### collect_changes.py 输出

```
REPO: /home/user/new-project
TOTAL: 2

=== 新增 ===

## [新增] README.md  (共 15 行)
# My Project
...

## [新增] src/main.py  (共 8 行)
print("hello")

=== END ===
```

### 技能生成结果

```
### README.md
docs: 添加项目 README
*理由：初始化项目，添加基本 README 说明。*

### src/main.py
feat: 创建程序入口
*理由：新建 main.py 作为项目入口，输出 hello。*
```

---

## 场景 3：合并冲突

假设合并时 `src/api/routes.py` 出现了冲突。

### collect_changes.py 输出

```
REPO: /home/user/my-project
TOTAL: 2
WARN: 1 个文件存在未解决的合并冲突，请先解决再提交

=== 修改 ===

## [修改] src/config/settings.py
@@ -5,3 +5,5 @@ DEBUG = True
+LOG_LEVEL = "INFO"
 ...

=== 合并冲突 ===

## [冲突] src/api/routes.py
(存在未解决的合并冲突标记，请先解决)

=== END ===
```

### 技能生成结果

```
⚠️ 1 个文件存在未解决的合并冲突，请先解决后再提交。

### src/config/settings.py
chore: 调整日志级别配置
*理由：在 settings.py 中新增 LOG_LEVEL 配置项，默认 INFO。*

### src/api/routes.py
⛔ 此文件有未解决的合并冲突，请先手动解决后再生成 commit message。
```

---

## 场景 4：同构批量文件（相似组聚合）

假设数据切割脚本产出了 `data/2015.json`…`data/2017.json` 三个结构一致的文件（另有一个 `misc/x1.txt`、`misc/x2.txt` 只有 2 个，不构成组）。

### collect_changes.py 输出

```
REPO: /home/user/my-project
TOTAL: 5

=== 新增 ===

>> SIMILAR_GROUP: data/#.json ×3（同构批量文件，建议聚合为一条 commit message）

## [新增] data/2015.json  (共 4 行)
{"year": 2015, "users": [
  {"id": 1, "name": "a"},
  {"id": 2, "name": "b"}
]}

## [新增] data/2016.json  (共 4 行)  [相似组，内容略]

## [新增] data/2017.json  (共 4 行)  [相似组，内容略]

## [新增] misc/x1.txt  (共 1 行)
x1

## [新增] misc/x2.txt  (共 1 行)
x2

=== END ===
```

（若某成员行数与代表相差悬殊，如 2019.json 有 200 行，脚本会改为详列该文件并标注 `[相似组，行数离群，已详列]`。）

### 技能生成结果

```
### data/（3 个文件：2015.json、2016.json、2017.json）
feat(data): 按年份切分数据为 2015–2017 共 3 份 JSON
*理由：切割脚本产物，3 份结构与字段一致（代表 2015.json 见采集输出）；适合合并为一次提交。*

### misc/x1.txt
docs: 添加杂项说明 x1
*理由：新增杂项文本文件。*

### misc/x2.txt
docs: 添加杂项说明 x2
*理由：新增杂项文本文件。*
```