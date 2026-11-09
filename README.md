# LexsitusSearcher

Standalone retrieval skill for the Lexsitus platform (CILRAP). It talks to the
public API at `cilrap-lexsitus.org` over direct HTTP; no browser, account or
institutional session is required.

## Install

Copy this folder into `~/.codex/skills/LexsitusSearcher` (the in-use location)
without the `.git` directory, then run the self-check:

```powershell
& "$env:USERPROFILE/.codex/skills/LexsitusSearcher/run.ps1" doctor
```

Python dependencies are `requests` and `beautifulsoup4`:

```powershell
python -m pip install -r requirements.txt
```

`run.ps1` searches, in order, for a Python with both packages: the skill's own
`venv`, the Codex bundled runtime, the WorkBuddy managed Python, then `python`
on `PATH`.

## Commands

```powershell
./run.ps1 search 'command responsibility' --tree Commentary --limit 10
./run.ps1 search 'genocide' --limit 5 --offset 5
./run.ps1 fetch '28-a-criminally-responsible' --text-out ./art28.txt
./run.ps1 trees --query 'genocide'
./run.ps1 doctor
```

See [SKILL.md](SKILL.md) for the behavioral boundaries and
[references/lexsitus-api.md](references/lexsitus-api.md) for the verified API
routes and observed response shapes.

## Notes

- The API is page-based. `--offset` must be a multiple of `--limit`.
- `--limit` is capped at 10. The public API changes its result set when
  `limit` grows: on 2026-10-18 one Commentary query returned an empty page 2 at
  `limit=50` while paging normally at `limit=10`. The Lexsitus frontend fixes
  `limit=10`.
- The API's `pagination.total`/`totalPages` fields are unreliable: on
  2026-10-18 a `genocide`/`Commentary` query reported `total=30` while pages
  1-4 returned 40 unique rows, and a `CaseLaw` query reported 22 while returning
  10 rows. The adapter keeps the raw value as `api_total` but ends pagination on
  an empty or short page.
- `Commentary` (CLICC) has a verified human reading route; other trees return
  API node URLs and metadata.
- Search matching is term-based, not phrase-based. A hit count is not a legal
  relevance judgment.

## 实测效果（2026-11-09）

以下命令与结果来自本机 `~/.codex/skills/LexsitusSearcher` 的实网运行；检索日期 2026-11-09（Asia/Shanghai），输出为该次运行实际返回的 JSON 报告。

```powershell
& .\run.ps1 search 'command responsibility' --tree Commentary --limit 5
```

- 状态：`ok`；`api_total = 15`，但 `api_pagination_reliable = false`，不能当作精确命中数；本次返回 5 条（`next_offset = 5`）。
- 代表性结果：

| 题名 | 类型 / 日期 | 链接 |
| --- | --- | --- |
| Article 28(1): Criminal Responsibility | DOCUMENT（Commentary）；—（API 未返回日期字段） | https://cilrap-lexsitus.org/en/clicc/28-a-criminally-responsible |
| Article 28(1): Military Commander | DOCUMENT（Commentary）；—（API 未返回日期字段） | https://cilrap-lexsitus.org/en/clicc/28-a-military-commander |
| Article 28(1): Effective Command and Control or Effective Authority and Control | DOCUMENT（Commentary）；—（API 未返回日期字段） | https://cilrap-lexsitus.org/en/clicc/28-a-effective-command-and-control-or-effective-authority-and-control |

> 说明：`api_total = 15` 不可当作精确命中数：`api_pagination_reliable = false`，报告自带的 `pagination_warning` 记录过 API 的 total/totalPages 与实际返回行数不一致（曾观察到 total=30 而第 1–4 页共 40 行）。正确做法是按 `next_offset` 继续翻页，遇到空页或短页即停。5 条结果全部是 `--tree Commentary`（CLICC 树）下的 Article 28 节点，`access = commentary-text` 表示评注正文可直接读取；它们是 CILRAP Lexsitus 平台的评注（次级材料），不是《罗马规约》条文本身，也不是判决全文。题名中的 `<mark>` 高亮标签已去除，其余文字与 JSON 逐字一致。
