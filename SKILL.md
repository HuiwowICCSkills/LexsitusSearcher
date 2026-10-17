---
name: lexsitus-searcher
description: 独立检索 Lexsitus（CILRAP 平台），用于查找罗马规约逐条评注（CLICC）、判例记录、犯罪要件与 digest、准备工作文件、TOAEP 馆藏和讲座；可按 treeKind 分树检索、逐页遍历并读取节点正文。不检索 CMN 主站或 Legal Tools 全库。
---

# LexsitusSearcher

> **`<skill-dir>`** = 本 SKILL.md 所在目录。核心脚本为 `<skill-dir>/scripts/lexsitus_search.py`；Windows 用 `<skill-dir>/run.ps1`，macOS/Linux 用 `<skill-dir>/run.sh`。接口细节见 [references/lexsitus-api.md](references/lexsitus-api.md)，部署见 [README.md](README.md)。

这个 skill 只做 Lexsitus 一件事，直接走 CILRAP 的公开 API，不需要浏览器或登录：

- `search`：检索 Lexsitus 内容树，返回真实条目、分页游标和每条记录的 `tree_kind`；不传 `--tree` 时跨全部树混合检索。
- `fetch`：按节点路径、API URL 或 `/en/clicc/<path>` 页面读取单个节点，返回正文、脚注 HTML、PDF/视频地址。
- `trees`：列出已观察到的 treeKind；加 `--query` 会逐树计数（有页数上限，超限时标为下界）。
- `doctor`：检查 API 可达性和 Python 依赖。

## 命令

```powershell
# 全树检索
& '<skill-dir>/run.ps1' search 'command responsibility' --limit 10 --out './lexsitus-search.json'

# 只查 CLICC 评注
& '<skill-dir>/run.ps1' search 'genocide' --tree Commentary --limit 10

# 翻页（offset 必须是 limit 的整数倍）
& '<skill-dir>/run.ps1' search 'genocide' --tree Commentary --limit 10 --offset 10

# 读取一个节点正文
& '<skill-dir>/run.ps1' fetch '28-a-criminally-responsible'
& '<skill-dir>/run.ps1' fetch 'https://cilrap-lexsitus.org/en/clicc/28-a-criminally-responsible' --text-out './art28.txt'

# 列出树；或统计某个词在各树的命中数
& '<skill-dir>/run.ps1' trees
& '<skill-dir>/run.ps1' trees --query 'genocide'

# 自检
& '<skill-dir>/run.ps1' doctor
```

通用参数：`--cache`、`--cache-ttl`、`--offline`、`--out`。`search` 另有 `--tree`、`--limit`（**1..10**，默认 10）、`--offset`、`--no-body`；`fetch` 另有 `--tree`（裸路径默认 Commentary）和 `--text-out`。

## 结果边界

- 这是 **Lexsitus 平台内**的检索，不是整个 CILRAP 站点、CMN 主站或 Legal Tools 全库。`CaseLaw` 行是映射记录，带 Legal Tools 编号和 PURL，不是判例全文。
- 匹配是**词项级**，不是短语级；命中处返回 `<mark>` 高亮。条文编号不入索引，查第 28 条请用路径或正文关键词。
- **API 的 `pagination.total` / `totalPages` 不可信**（2026-10-18 实测：报 `total=30`，逐页实际取得 40 条；另一查询报 22 却只返回 10 条）。报告保留 `api_total` 供核对，但分页结束以空页或短页为准；不要把 `api_total` 当精确命中数。
- **`limit` 会改变结果集本身**：同一查询在 `limit=50` 时可能第 2 页直接为空，在 `limit=10` 时却能正常翻到第 4 页。官方前端固定 `limit=10`，本 skill 因此只接受 1..10，超出即报错。
- **官方 UI 也用这个错误计数算页数**：2026-10-18 浏览器实测，`genocide` + CLICC 只显示 1–3 页（API 第 4 页仍有 10 条）；Case Law 显示 1–3 页，但第 2 页即 "No results found"。因此官方界面本身会少显示或多给空页。
- `trees --query` 在 `limit=10` 下逐页计数，到 `--max-pages` 上限时标为下界；即使未到上限也标 `count_is_reliable=false`，因为 API 可能自行截断。
- 只有 `Commentary`（CLICC）的人读页面 `/en/clicc/<path>` 经过验证；其他树返回 API 节点链接和元数据。正文能否取得，以返回的 `text_characters` 为准。
- 多词查询可能只命中其中一个词，必须按 `title`、`snippet` 和 `tree_kind` 判断相关性，不能把命中数当法律相关性判断。
- 报告里的 `evidence` 记录实际请求 URL、HTTP 状态、内容类型、字节响应哈希和检索时间。引用评注时以 `fetch` 取回的正文为准，不用搜索摘要代替正文。
- Lexsitus 内容是**研究参考/学术评注**，不是拘束力来源；与规约、判例正文分开标注。

## 参考

- 2026-10-18 实测（检索路由、参数语义、节点返回结构、分页与匹配行为）：[references/lexsitus-api.md](references/lexsitus-api.md)
- 部署、运行环境与排错：[README.md](README.md)
