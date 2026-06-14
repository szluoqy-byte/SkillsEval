# 静态扫描规则详细设计

## 1. 文档目标

本文详细描述 SkillsEval 当前 Static Scan 的规则体系、执行逻辑、评分方式、证据输出与每一条规则的定义。

实现入口：

```text
backend/app/static_scanner.py
```

任务编排入口：

```text
backend/app/evaluator.py
```

前端展示位置：

```text
Task Detail -> 评测证据 / 运行产物 -> Scan
```

## 2. 扫描定位

Static Scan 是 SkillsEval 三类指标之一，负责回答：

- Skill 包结构是否完整。
- `SKILL.md` 是否符合基本规范。
- 名称、描述、frontmatter 是否可被平台稳定识别。
- Skill 是否引用不存在、越界、绝对路径文件。
- Skill 是否包含明显安全风险。
- Skill 是否声明或暗示过高权限。

Static Scan 不负责判断 Skill 是否真的会被模型调用，也不负责判断任务输出质量。这两类问题分别由 Trigger 与 Effect 处理。

## 3. 执行时机

当前只在 Evaluation Task 的 `static_scan` 阶段执行。

上传导入阶段只做：

- ZIP 解压。
- `SKILL.md` 定位。
- `skill_name` 预填。
- Import Draft 创建。

上传导入阶段不会因为 Static Scan 规则命中而阻断确认。

## 4. 扫描输入与输出

输入：

- `artifact_root`：Skill 版本包的本地目录。
- `manifest`：导入阶段记录的元数据，当前主要用于判断 `SKILL.md` 所在父目录是否与 frontmatter `name` 一致。

输出：

```json
{
  "score": 87.0,
  "status": "warning",
  "summary": "Static scan found 1 major and 1 minor findings.",
  "metrics": {
    "critical_count": 0,
    "major_count": 1,
    "minor_count": 1,
    "info_count": 0,
    "total_findings": 2,
    "rules_evaluated": 53,
    "files_scanned": 4
  },
  "findings": [],
  "rules": []
}
```

写入位置：

- `stage_results.stage = static_scan`
- `findings`
- `skill_versions.static_scan_status`
- `evidence_items`

Artifact：

```text
data/runs/<run_id>/static/findings.json
data/runs/<run_id>/static/static_metrics.json
```

## 5. 评分与状态

评分公式：

```text
scan_score = clamp(
  100
  - critical_count * 25
  - major_count * 10
  - minor_count * 3
  - info_count * 1,
  0,
  100
)
```

状态规则：

| 状态 | 条件 | 产品展示建议 |
| --- | --- | --- |
| `critical` | `critical_count > 0` | Critical risk |
| `warning` | 无 critical，但存在 major 或 minor | Findings |
| `passed` | 无 critical / major / minor | No active findings |

产品文案注意：

- 不建议说整个 Skill “通过/失败”。
- 建议表达为“发现风险”“无活跃 findings”“需复核”。

## 6. 扫描文件范围

`static_scanner.py` 只读取文本类文件：

- `.md`
- `.txt`
- `.json`
- `.yaml`
- `.yml`
- `.toml`
- `.py`
- `.sh`
- `.js`
- `.ts`
- `.bash`
- `.env`
- `SKILL.md`
- `skill.md`
- `README.md`

安全与权限扫描只扫描：

- root 下一级文件。
- `scripts/` 下文件。
- `agents/` 下文件。

这样避免递归读取无关大目录，同时覆盖 MVP 常见 Skill 包结构。

## 7. Frontmatter 解析规则

当前使用标准库实现最小 YAML-like parser。

支持：

- 顶层 `key: value`
- 一层 mapping：

```yaml
metadata:
  owner: qa
  source: internal
```

支持 scalar：

- 字符串
- 引号字符串
- `true` / `false`

不支持完整 YAML 语法，例如复杂数组、多文档、锚点等。

允许字段：

```text
name
description
license
allowed-tools
metadata
compatibility
```

## 8. 规则清单总览

当前共 53 条规则，分组如下：

| 分组 | 数量 | 关注点 |
| --- | ---: | --- |
| `STRUCT-*` | 2 | Skill 包结构 |
| `FRONTMATTER-*` | 7 | YAML frontmatter |
| `NAME-*` | 10 | Skill name |
| `DESCRIPTION-*` | 3 | 描述字段 |
| `OPTIONAL-*` | 5 | 可选字段 |
| `BODY-*` | 3 | SKILL.md 正文 |
| `FILE-*` | 5 | 文件引用 |
| `AWS-STR-*` | 5 | 结构与描述质量 |
| `AWS-SEC-*` | 9 | 安全风险 |
| `AWS-PERM-*` | 4 | 权限风险 |

说明：规则编号保持与当前实现一致，便于 finding code、测试用例和前端展示对齐。

## 9. STRUCT 结构规则

### STRUCT-001：Skill 包根必须是目录

- 类别：Structure
- 严重级别：critical
- 触发条件：`artifact_root` 不存在，或存在但不是目录。
- 检查位置：artifact root。
- 风险说明：后续无法定位 `SKILL.md`、引用文件和脚本。
- 修复建议：将 Skill 打包为一个目录，并确保目录中包含 `SKILL.md`。

### STRUCT-002：必须存在 SKILL.md

- 类别：Structure
- 严重级别：critical
- 触发条件：根目录下不存在 `SKILL.md` 或 `skill.md`。
- 检查位置：artifact root。
- 风险说明：Runner 无法读取 Skill 主入口，平台无法解析 Skill 元数据。
- 修复建议：在 Skill 根目录添加 `SKILL.md`。

## 10. FRONTMATTER 元数据规则

### FRONTMATTER-001：SKILL.md 必须以 YAML frontmatter 开始

- 类别：Frontmatter
- 严重级别：critical
- 触发条件：`SKILL.md` 去除开头空白后不是以 `---` 开始。
- 风险说明：平台无法稳定解析 name、description、allowed-tools 等元数据。
- 修复建议：在 `SKILL.md` 顶部添加 `---` 包裹的 frontmatter。

### FRONTMATTER-002：YAML frontmatter 必须闭合

- 类别：Frontmatter
- 严重级别：critical
- 触发条件：存在开头 `---`，但没有后续闭合 `---`。
- 风险说明：正文和元数据边界不明确，后续规则可能误判。
- 修复建议：在 frontmatter 字段之后添加闭合 `---`。

### FRONTMATTER-003：YAML frontmatter 必须可解析

- 类别：Frontmatter
- 严重级别：critical
- 触发条件：frontmatter 中存在无法解析的行，例如缺少 `:`、嵌套行格式错误、空 key。
- 风险说明：元数据结构不可用。
- 修复建议：使用简单 key-value YAML frontmatter。

### FRONTMATTER-004：YAML frontmatter 顶层必须是 mapping

- 类别：Frontmatter
- 严重级别：critical
- 触发条件：frontmatter 顶层以 list item 等非 mapping 形式出现。
- 风险说明：平台需要按字段读取元数据，非 mapping 无法映射。
- 修复建议：使用顶层 key-value 字段。

### FRONTMATTER-005：必须存在 name

- 类别：Frontmatter
- 严重级别：critical
- 触发条件：frontmatter 缺少 `name`。
- 风险说明：无法建立 Skill 唯一身份。
- 修复建议：添加 `name` 字段。

### FRONTMATTER-006：必须存在 description

- 类别：Frontmatter
- 严重级别：critical
- 触发条件：frontmatter 缺少 `description`。
- 风险说明：Skill 缺少可用于发现、榜单和人工复核的能力说明。
- 修复建议：添加 `description` 字段。

### FRONTMATTER-007：不允许未知字段

- 类别：Frontmatter
- 严重级别：critical
- 触发条件：frontmatter 中出现不在允许列表内的字段。
- 允许字段：`name`、`description`、`license`、`allowed-tools`、`metadata`、`compatibility`。
- 风险说明：未知字段可能来自不兼容规范，影响跨运行时解析。
- 修复建议：删除未知字段，或迁移到 `metadata`。

## 11. NAME 命名规则

### NAME-001：name 必须是字符串

- 类别：Name
- 严重级别：critical
- 触发条件：`name` 不是字符串，例如 boolean 或 mapping。
- 修复建议：设置为非空小写字符串。

### NAME-002：name 不能为空

- 类别：Name
- 严重级别：critical
- 触发条件：`name.strip()` 为空。
- 修复建议：设置清晰、稳定、可读的 Skill 名。

### NAME-003：name 必须 NFKC 归一后不变

- 类别：Name
- 严重级别：critical
- 触发条件：`unicodedata.normalize("NFKC", name)` 与原值不同。
- 风险说明：Unicode 兼容字符可能造成显示与唯一性判断不一致。
- 修复建议：使用归一化后的名称。

### NAME-004：name 长度必须为 1-64 字符

- 类别：Name
- 严重级别：critical
- 触发条件：归一化后的 name 超过 64 字符。
- 修复建议：缩短名称。

### NAME-005：name 必须小写

- 类别：Name
- 严重级别：critical
- 触发条件：`name != name.lower()`。
- 修复建议：全部使用小写字符。

### NAME-006：name 只能包含字母数字和连字符

- 类别：Name
- 严重级别：critical
- 触发条件：name 中存在非 alphanumeric 且非 `-` 的字符。
- 风险说明：空格、下划线、特殊符号会影响路径、路由和跨平台兼容。
- 修复建议：只使用小写字母、数字和 `-`。

### NAME-007：name 不能以连字符开头

- 类别：Name
- 严重级别：critical
- 触发条件：name 以 `-` 开头。
- 修复建议：移除开头连字符。

### NAME-008：name 不能以连字符结尾

- 类别：Name
- 严重级别：critical
- 触发条件：name 以 `-` 结尾。
- 修复建议：移除结尾连字符。

### NAME-009：name 不能包含连续连字符

- 类别：Name
- 严重级别：critical
- 触发条件：name 包含 `--`。
- 修复建议：将连续连字符替换为单个连字符。

### NAME-010：name 应与 Skill 目录名一致

- 类别：Name
- 严重级别：critical
- 触发条件：导入 manifest 中的 `skill_md_path` 有父目录，且父目录名与 frontmatter `name` 不一致。
- 风险说明：运行时和包管理通常以目录名或 name 作为 Skill 标识，不一致会导致触发和引用混乱。
- 修复建议：统一目录名和 frontmatter `name`。

## 12. DESCRIPTION 描述规则

### DESCRIPTION-001：description 必须是字符串

- 类别：Description
- 严重级别：critical
- 触发条件：`description` 不是字符串。
- 修复建议：设置为非空字符串。

### DESCRIPTION-002：description 不能为空

- 类别：Description
- 严重级别：critical
- 触发条件：`description.strip()` 为空。
- 修复建议：写一句清晰的能力描述。

### DESCRIPTION-003：description 长度必须为 1-1024 字符

- 类别：Description
- 严重级别：critical
- 触发条件：description 超过 1024 字符。
- 风险说明：过长描述不适合列表、榜单和模型上下文。
- 修复建议：缩短到 1024 字符以内。

## 13. OPTIONAL 可选字段规则

### OPTIONAL-002：compatibility 必须是字符串

- 类别：Optional Fields
- 严重级别：major
- 触发条件：提供了 `compatibility`，但类型不是字符串。
- 修复建议：改为字符串，或删除该字段。

### OPTIONAL-003：compatibility 长度必须为 1-500 字符

- 类别：Optional Fields
- 严重级别：major
- 触发条件：`compatibility` 超过 500 字符。
- 修复建议：压缩为简短兼容性说明。

### OPTIONAL-004：compatibility 提供后不能为空

- 类别：Optional Fields
- 严重级别：critical
- 触发条件：提供了 `compatibility`，但为空字符串。
- 修复建议：删除该字段或填写有效内容。

### OPTIONAL-006：metadata 应该是 mapping

- 类别：Optional Fields
- 严重级别：major
- 触发条件：提供了 `metadata`，但类型不是 mapping。
- 修复建议：使用 key-value mapping。

### OPTIONAL-008：allowed-tools 必须是空格分隔字符串

- 类别：Optional Fields
- 严重级别：critical
- 触发条件：提供了 `allowed-tools`，但类型不是字符串。
- 风险说明：权限扫描依赖该字段解析工具列表。
- 修复建议：使用空格分隔字符串，例如 `Read Grep Bash(git:*)`。

## 14. BODY 正文规则

### BODY-001：SKILL.md 正文不能为空

- 类别：Body
- 严重级别：critical
- 触发条件：frontmatter 闭合后的正文为空。
- 风险说明：Skill 没有可执行说明或使用指引。
- 修复建议：在 frontmatter 后补充 Skill 说明。

### BODY-002：SKILL.md 建议少于 500 行

- 类别：Body
- 严重级别：major
- 触发条件：`SKILL.md` 超过 500 行。
- 风险说明：主说明过长会降低可维护性和上下文加载效率。
- 修复建议：将长参考内容拆到引用文件。

### BODY-003：说明 token 估算建议少于 5000

- 类别：Body
- 严重级别：major
- 触发条件：按非空白 token 粗略估算超过 5000。
- 风险说明：过大上下文影响模型加载和成本。
- 修复建议：压缩主说明，细节移动到 references。

## 15. FILE 文件引用规则

引用提取来源：

- Markdown 链接：`[text](path)`
- 反引号路径：`` `references/...` ``、`` `scripts/...` ``、`` `assets/...` ``、`` `agents/...` ``

### FILE-001：文件引用必须是相对路径

- 类别：File Reference
- 严重级别：critical
- 触发条件：引用以 `/`、`~/` 或 Windows 盘符开头。
- 风险说明：绝对路径不可移植，也可能泄露本机路径。
- 修复建议：改为相对 Skill root 的路径。

### FILE-003：引用文件必须存在

- 类别：File Reference
- 严重级别：critical
- 触发条件：引用路径在 artifact root 下不存在。
- 风险说明：模型或用户按说明访问文件时会失败。
- 修复建议：补齐文件或修改引用。

### FILE-004：引用不能逃逸 Skill root

- 类别：File Reference
- 严重级别：critical
- 触发条件：引用路径包含 `..`，或 resolve 后不在 artifact root 内。
- 风险说明：可能访问包外文件，存在安全风险。
- 修复建议：只引用 Skill 包内文件。

### FILE-005：引用深度建议不超过两级

- 类别：File Reference
- 严重级别：minor
- 触发条件：引用路径有效片段超过 2 个，例如 `references/a/b/c.md`。
- 风险说明：过深目录降低可读性和维护性。
- 修复建议：扁平化引用目录。

### FILE-006：避免深层引用链

- 类别：File Reference
- 严重级别：minor
- 触发条件：从 `SKILL.md` 引用的 Markdown 文件继续引用其他 Markdown，链路深度超过 2。
- 风险说明：模型可能需要多跳读取才能理解 Skill，触发不稳定。
- 修复建议：让 `SKILL.md` 直接引用关键文件，减少多跳链路。

## 16. AWS-STR 结构与描述质量规则

### AWS-STR-016：README.md 与 SKILL.md 并存可能混淆入口

- 类别：Structure Quality
- 严重级别：minor
- 触发条件：根目录同时存在 `SKILL.md` 和 `README.md`。
- 风险说明：用户或模型可能不清楚哪个是主入口。
- 修复建议：保持 README 简短，或将详细内容移动到 SKILL.md/references。

### AWS-STR-017：脚本建议包含 shebang

- 类别：Script Quality
- 严重级别：minor
- 触发条件：`scripts/` 下 `.py` 或 `.sh` 文件第一行不是 `#!`。
- 风险说明：脚本独立执行时解释器不明确。
- 修复建议：添加 shebang，例如 `#!/usr/bin/env python3`。

### AWS-STR-018：Skill name 不应包含保留词

- 类别：Structure Quality
- 严重级别：major
- 触发条件：name 包含 `anthropic` 或 `claude`。
- 风险说明：容易产生厂商归属误导或命名冲突。
- 修复建议：移除厂商保留词。

### AWS-STR-019：description 不应包含 XML/HTML 标签

- 类别：Description Quality
- 严重级别：major
- 触发条件：description 匹配 `<tag>` 形式。
- 风险说明：描述字段用于展示和模型理解，标记语言可能导致展示异常或注入风险。
- 修复建议：移除 HTML/XML 标签。

### AWS-STR-020：description 避免第一/第二人称表达

- 类别：Description Quality
- 严重级别：minor
- 触发条件：description 包含类似 `I can`、`we can`、`you can`。
- 风险说明：描述应表达能力本身，而不是对话式承诺。
- 修复建议：改为能力导向描述。

## 17. AWS-SEC 安全规则

### AWS-SEC-001：疑似硬编码密钥

- 类别：Security
- 严重级别：critical
- 触发条件：
  - `api_key/token/password/secret = "..."` 且值长度较长。
  - 私钥头。
  - 带用户名密码的数据库 URL。
  - `sk-` 开头的长 token。
- 例外：包含 `example`、`dummy`、`test`、`placeholder`、`your_api_key`、`changeme` 的示例值。
- 修复建议：删除密钥，改用环境变量或密钥管理。

### AWS-SEC-002：外部 URL 或 endpoint

- 类别：Security
- 默认严重级别：major
- 触发条件：文本中出现非安全列表域名的 `http(s)` URL。
- 安全列表：`example.com`、`example.org`、`localhost`、`127.0.0.1`。
- 降级条件：注释行或 Markdown 文档中的 URL 按 minor 记录。
- 风险说明：外部 endpoint 可能带来数据泄露或供应链风险。
- 修复建议：说明必要性，或移除不必要 endpoint。

### AWS-SEC-003：命令或动态代码执行

- 类别：Security
- 严重级别：major
- 触发条件：脚本文件中出现：
  - `subprocess.run/call/Popen/check_output`
  - `os.system`
  - `os.popen`
  - `shell=True`
  - `eval(`
  - `exec(`
- 修复建议：避免执行 shell 命令或用户提供代码，改用受控 API。

### AWS-SEC-004：不安全依赖安装

- 类别：Security
- 默认严重级别：critical 或 major
- 触发条件：
  - `curl|wget ... | sh|bash|zsh`：critical。
  - `pip install` 但不是 `pip install -r`：major。
  - `npm install`：major。
- 风险说明：运行时拉取依赖存在供应链不可控风险。
- 修复建议：使用锁文件、requirements 文件和固定版本。

### AWS-SEC-005：Prompt injection surface

- 类别：Security
- 严重级别：major
- 触发条件：文本暗示无约束处理用户输入、执行用户提供代码/命令、写入任意用户路径。
- 风险说明：Skill 可能把不可信输入直接交给模型或系统执行。
- 修复建议：明确输入边界、校验策略和输出约束。

### AWS-SEC-006：不安全反序列化

- 类别：Security
- 默认严重级别：critical 或 major
- 触发条件：
  - `pickle.load/loads`
  - `cPickle.load/loads`
  - `marshal.load/loads`
  - `shelve.open`
  - `yaml.load` 且未使用 `safe_load` 或 `SafeLoader`
- severity：
  - pickle/marshal/shelve：critical。
  - yaml.load without SafeLoader：major。
- 修复建议：使用 JSON、`yaml.safe_load` 或其他安全解析器。

### AWS-SEC-007：动态 import 或代码生成

- 类别：Security
- 严重级别：major
- 触发条件：
  - `importlib.import_module(`
  - `__import__(`
  - `compile(`
- 风险说明：动态加载路径难以审计，可能加载不可信模块。
- 修复建议：使用静态 import 和明确依赖列表。

### AWS-SEC-008：Base64 payload 或混淆

- 类别：Security
- 默认严重级别：major，特定情况 critical
- 触发条件：
  - `base64.b64decode`
  - `base64.decodebytes`
  - `atob(`
  - 长度超过 120 的 base64-like 字符串。
- 升级条件：同一文件出现 base64 decode 且出现 `eval(` 或 `exec(`，记为 critical。
- 风险说明：混淆 payload 可能隐藏真实行为。
- 修复建议：移除混淆内容，不要 decode 后执行。

### AWS-SEC-009：MCP 供应链风险

- 类别：Security
- 默认严重级别：major，`npx -y` 为 critical
- 触发条件：
  - `mcpServers`
  - `mcp_servers`
  - `npx -y`
  - 指向 `/mcp` 或 `/sse` 的 URL。
- 风险说明：MCP server 可能引入外部执行和数据流风险。
- 修复建议：审查 MCP server 来源，避免隐式执行外部包。

## 18. AWS-PERM 权限规则

### AWS-PERM-001：allowed-tools 授予无限制 shell

- 类别：Permission
- 严重级别：major
- 触发条件：`allowed-tools` 包含：
  - `bash`
  - `bash(*)`
  - `shell`
  - `terminal`
- 风险说明：Skill 可以执行广泛本机命令。
- 修复建议：缩小 shell 权限范围，或移除。

### AWS-PERM-002：allowed-tools 包含高风险工具

- 类别：Permission
- 严重级别：minor
- 触发条件：工具前缀包含：
  - `bash`
  - `shell`
  - `execute`
  - `httprequest`
  - `terminal`
- 修复建议：复核工具必要性，减少权限。

### AWS-PERM-003：allowed-tools 数量过多

- 类别：Permission
- 严重级别：minor
- 触发条件：解析出的工具数量超过 15。
- 风险说明：权限面过宽，难以解释 Skill 实际需要。
- 修复建议：只保留最小必要工具。

### AWS-PERM-004：文本暗示敏感权限需求

- 类别：Permission
- 默认严重级别：major 或 minor
- 触发条件：文本包含：
  - `~/.ssh`
  - `~/.aws`
  - `~/.kube`
  - `/etc/passwd`
  - `sudo`
  - `root access`
  - `credentials`
  - `password`
  - `token`
  - `private key`
  - `0.0.0.0`
  - `all interfaces`
- severity：
  - 涉及 ssh/aws/kube/sudo/root/credentials/password/token/private key：major。
  - 绑定所有网卡等网络暴露：minor。
- 修复建议：移除敏感访问，或明确权限边界和最小化访问方式。

## 19. 前端展示设计

Scan evidence tab 应分为两个视角：

- `Findings`：默认视角，只展示命中的规则。
- `Passed Rules`：辅助视角，展示未命中的规则。

Finding 展示字段：

- rule id
- severity
- title
- detail
- file path
- line number
- fix

规则通过视角展示字段：

- rule id
- category
- item
- severity
- title

目的：

- 普通用户优先看到需要处理的问题。
- 测试人员可以复核每条规则是否被执行。
- 平台运营可以确认规则覆盖范围。

## 20. 与 Recommendation 的关系

Static Scan 不阻断 Trigger 和 Effect。

影响策略：

- critical finding：recommendation 最高为 `review_required`。
- warning finding：通常为 `review_required`。
- 无 active finding：满足进入 `usable` 或 `recommended` 的必要条件之一。

## 21. 当前边界与后续增强

当前不支持：

- 规则开关。
- ignore / allowlist。
- 上传阶段阻断。
- 用户自定义规则。
- 完整 YAML parser。
- SARIF 导出。

后续可增强：

- 每条规则配置启停。
- 项目级 allowlist。
- SARIF / JSON Schema 输出。
- 前端规则详情页。
- 规则版本号与迁移策略。
