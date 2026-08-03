# 来源检查历史设计

## 目标

让每日求职流程同时记住两件不同的事：哪些岗位已经被筛选过，以及哪些搜索来源页面已经被检查过。岗位记录继续负责岗位级去重和筛选状态；新增的来源检查历史负责防止在没有产生岗位、或搜索结果为空时重复检查同一个来源页面。

## 范围与约束

- 只使用本地 SQLite，不增加云端服务、账号系统或后台定时任务。
- 不保存密码、Cookie、浏览器会话、简历正文或其他认证材料。
- 来源检查只记录用户或 Codex 已经实际打开并检查过的 URL；插件不把搜索摘要或推测当作检查成功。
- 同一个来源 URL 默认以 24 小时为新鲜期；用户改变搜索条件、发现页面有实质更新，或明确要求强制重查时，可以再次检查。
- 来源检查状态不改变任何岗位的 `screening_status` 或 `application_status`。

## 数据模型

新增 `source_checks` 表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER PRIMARY KEY | 本地检查记录编号 |
| `source` | TEXT NOT NULL | 规范化来源名称，例如 `company`、`greenhouse`、`boss` |
| `url` | TEXT NOT NULL | 去掉追踪参数和片段后的规范化 URL |
| `checked_at` | TEXT NOT NULL | ISO-8601 UTC 检查时间 |
| `result_count` | INTEGER NOT NULL | 本次页面解析出的岗位数量，允许为 0 |
| `status` | TEXT NOT NULL | `ok`、`empty`、`warning` 或 `unreadable` |
| `warnings_json` | TEXT NOT NULL | 解析或访问警告数组；只保存文字，不保存页面凭据或原始浏览器输出 |

每一次实际检查都保留一条历史记录；不覆盖历史。查询“是否需要检查”时只看同一 `source + url` 的最新记录。URL 使用现有 `canonical_url()` 规则规范化，因而跟踪参数不会绕过来源历史。

## 本地接口

`JobStore` 新增以下方法：

- `record_source_check(source, url, checked_at, result_count, status, warnings) -> SourceCheckRecord`
- `latest_source_check(source, url) -> SourceCheckRecord | None`
- `source_check_is_fresh(source, url, max_age_hours=24, now=None) -> bool`
- `list_source_checks(source=None, limit=None) -> list[SourceCheckRecord]`

输入必须校验：URL 必须是 HTTPS、结果数量不得为负数、状态必须属于四个允许值、警告必须是字符串数组。返回记录中的 URL 必须是规范化后的 URL。

## CLI 与技能流程

新增 `source-check` 命令组：

```text
job_search_agent.py source-check record --source company --url URL \
  --result-count 3 --status ok --checked-at 2026-08-04T00:00:00+00:00
job_search_agent.py source-check status --source company --url URL --max-age-hours 24
job_search_agent.py source-check list --source company --format json
```

- `record` 在浏览器或搜索工具完成一次真实检查后调用；它不会自行访问网络。
- `status` 返回规范化 URL、最新检查时间、结果数量、状态和 `fresh` 布尔值；没有历史时返回 `fresh: false`。
- `list` 返回本地来源检查历史，按最近检查时间倒序排列。
- `--force` 不需要写入数据库；强制重查的语义由技能在发现来源发生变化时直接再次打开页面并记录新的检查。

`job-discovery` 和 `job-search-workflow` 技能在打开来源前查询 `status`，在完成页面检查后记录 `record`。岗位导入仍然使用现有 `ingest`，因此“页面已检查”和“岗位已导入/已筛选”保持两个独立步骤。

## 导入、导出与隐私

- JSON 导出增加 `source_checks` 数组；Markdown 导出增加一个来源检查摘要区，不包含浏览器原始内容。
- JSON 导入按 `source + url + checked_at + status + result_count + warnings_json` 幂等去重，重复导入不会制造重复检查记录。
- 旧数据库通过 `CREATE TABLE IF NOT EXISTS` 自动升级，无需迁移脚本。
- 来源 URL 仍可能包含用户的搜索关键词，因此只写入本地数据库；公共发布包和测试夹具不得包含真实来源检查记录。

## 错误与边界

- URL 无效、使用 HTTP、包含用户名密码或片段时，`record` 失败且不写入记录。
- `unreadable` 和 `warning` 仍然算作“确实检查过”，但不会证明岗位仍在招聘；技能必须把警告展示给用户。
- 旧来源历史只用于减少重复检查，不能替代当前职位详情页的开放性验证。
- 来源检查记录的删除不在本次范围内，避免误删审计历史；用户可以通过删除整个本地数据库来清除本地数据。

## 验证标准

必须有自动测试证明：

1. 同一规范化 URL 的追踪参数不会产生新的来源身份。
2. 空结果页可以被记录，且 24 小时内状态为 `fresh`。
3. 超过新鲜期、不同 URL、不同来源或明确传入不同当前时间时会重新变为待检查。
4. 无效 URL、负数结果数和未知状态被拒绝且数据库不变。
5. 来源检查记录能被导出并幂等导入，导出不包含凭据或本机路径。
6. 现有岗位去重、筛选队列、投递授权和发布包测试继续通过。
