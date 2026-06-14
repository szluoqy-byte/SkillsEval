# Skill Static Scan Rules Design

## Summary

静态扫描用于在评测任务的 `static_scan` 阶段判断 Skill 包是否安全、完整、可维护、可评测。MVP 不在上传导入阶段阻断用户确认 Skill，也不提供 ignore/allowlist；扫描结论进入任务报告、stage result、findings 和本地 artifact。

规则来源分两类：

- Spec / skills-ref 兼容性规则：结构、frontmatter、name、description、可选字段、正文、文件引用。
- AWS 风格质量与安全规则：结构质量、脚本质量、安全风险、权限风险、供应链风险。

## Runtime Design

扫描入口是 `backend/app/static_scanner.py` 的 `scan_skill_version(artifact_root, manifest)`。评测任务运行时，`backend/app/evaluator.py` 读取 `skill_versions.artifact_root` 和 `manifest`，在 `static_scan` 阶段执行真实扫描。

输出复用现有数据模型：

- `stage_results`：写入 `stage=static_scan`、`score`、`summary`、`metrics` 和 `artifact_path`。
- `findings`：每条规则命中写入 `code`、`severity`、`title`、`detail`、`file_path`、`line_number`、`fix`。
- `evidence_items`：登记 `static/findings.json` 和 `static/static_metrics.json`。
- `skill_versions.static_scan_status`：按扫描结果更新为内部枚举 `passed | warning | critical`；产品展示为 `No active findings | Findings | Critical risk`，避免把 Skill 整体表达成 pass/fail。

Artifact 目录：

```text
runs/<run_id>/static/
  findings.json
  static_metrics.json
```

## Rule Model

每条规则在注册表中声明：

- `rule_id`
- `category`
- `item`
- `severity`
- `title`
- `fix`

Severity 归一：

- 附件中的 `Critic` 统一为 `critical`。
- `Major` 统一为 `major`。
- `Minor` 统一为 `minor`。
- 保留 `info` 作为后续低风险提示级别。

MVP 覆盖规则组：

- `STRUCT-*`
- `FRONTMATTER-*`
- `NAME-*`
- `DESCRIPTION-*`
- `OPTIONAL-*`
- `BODY-*`
- `FILE-*`
- `AWS-STR-*`
- `AWS-SEC-*`
- `AWS-PERM-*`

严格度：

- 可选字段不存在不报错。
- 可选字段一旦提供，必须满足 strict spec。例如 `compatibility` 不能为空，`allowed-tools` 必须是空格分隔字符串。
- `BODY-001` 按 strict spec 执行，空正文是 critical finding。

## Scan Metric

Scan 分：

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

扫描状态：

```text
critical: critical_count > 0
warning: major_count > 0 或 minor_count > 0
passed: 无 critical / major / minor，前端展示为 No active findings
```

## Recommendation Policy

命中 critical finding 不阻断后续 Trigger 评测，但 Scan 作为独立风险指标展示。

最终推荐等级：

```text
usable: Scan 无 critical 且 Trigger >= 80
review_required: 存在 Scan warning/critical，或 Trigger 在 50-79
not_recommended: Trigger < 50，或没有 Trigger Queries，或运行失败
```

如果存在任一 critical finding，推荐等级最高为 `review_required`。平台不再把 Scan、Trigger、Effect 合并为单一 overall 分。

## MVP Boundaries

- 不新增数据库表。
- 不新增规则开关、ignore、allowlist。
- 不在上传确认后自动扫描。
- 不阻断动态评测。
- Frontmatter 使用标准库最小解析器，覆盖当前规则所需的 key-value 和一层 mapping；后续如需完全 YAML 兼容再引入 `PyYAML`。
