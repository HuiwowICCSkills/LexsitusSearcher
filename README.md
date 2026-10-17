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
