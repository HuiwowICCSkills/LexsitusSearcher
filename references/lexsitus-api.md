# Lexsitus API notes

Verified 2026-10-18 against the public endpoints, direct HTTP, no login.

## Routes

```text
GET https://cilrap-lexsitus.org/api/v1/search
GET https://cilrap-lexsitus.org/api/v1/nodes/path/{path}?treeKind={kind}&lang=en
GET https://cilrap-lexsitus.org/en/clicc/{path}
```

The domain is `cilrap-lexsitus.org`. `lexsitus.org` is not the API host.

## Search parameters

| Parameter | Meaning |
|---|---|
| `query` | required; an empty value returns HTTP 400 `{"error":"Search query is required"}` |
| `page` | 1-based page number |
| `limit` | page size; the adapter allows 1..50 |
| `treeKind` | optional tree filter |

Because the API pages rather than offsets, `page = offset // limit + 1` and
`offset` must be a multiple of `limit`.

Response:

```json
{
  "results": [ ... ],
  "pagination": {"total": 0, "page": 1, "limit": 1, "totalPages": 0}
}
```

**The `pagination.total` and `totalPages` values are unreliable.** Measured
2026-10-18 with `query=genocide&treeKind=Commentary`:

| `limit` | page 1..4 rows | reported `total` | reported `totalPages` |
|---|---|---|---|
| 1 | 1, 1, 1, 1 | 3 | 3 |
| 3 | 3, 3, 3, 3 | 9 | 3 |
| 10 | 10, 10, 10, 10 | 30, 30, 30, 13 | 3, 3, 3, 2 |

Pages 1-4 at `limit=10` returned 40 distinct rows, and page 5 was empty,
although the API never reported more than 30. The adapter therefore advances
`next_offset` only while a full page is returned and ignores the reported total
for end-of-results decisions. `trees --query` counts rows by paging, not from
`pagination.total`.

## Observed tree kinds

`Commentary` (CLICC), `RPECommentary`, `CaseLaw`, `RomeStatute`,
`ElementsOfCrime`, `ElementsOfCrimeDigest`, `MeansOfProofDigest`,
`PreparatoryWork`, `TOAEP`, `Lectures`.

Without `treeKind` the API mixes all of them. Each record carries its own
`treeKind`, so the adapter always preserves it.

## Record mapping

- `document.richTextDocument.body` — HTML body with footnotes and original
  citations; this is the commentary text.
- `document.pdfDocument.pdfUrl` — PDF where the node has one.
- `document.videoDocument.videoUrl` — lecture recordings.
- `description` — metadata blocks for lectures and case records; not body text.

`CaseLaw` rows are mappings to Legal Tools records: the description carries a
`Database Record Number` and a `legal-tools.org/doc/<slug>/` persistent URL. The
row is a findable record, not the judgment full text.

Only `Commentary` has a verified human reading route
(`/en/clicc/<path>`); other trees keep the API node URL.

## Node read response

`GET /api/v1/nodes/path/28-a-criminally-responsible?treeKind=Commentary&lang=en`
returned HTTP 200 with, among other fields:

```json
{
  "id": "cmd2v70qy11a9f1cwk7p4eu2f",
  "title": "Article 28(1): Criminal Responsibility",
  "path": "28-a-criminally-responsible",
  "treeKind": "Commentary",
  "type": "DOCUMENT",
  "updatedAt": "2026-08-27T11:12:22.269Z",
  "parent": {"path": "28-a"},
  "children": [],
  "document": {
    "richTextDocument": {"body": "<p>...</p>"},
    "pdfDocument": null
  }
}
```

## Matching behavior

- Matching is term-based, and hits are returned with `<mark>` highlighting in
  `title` and `description`; it is not exact-phrase search.
- Query `CMN Knowledge Hub` returned a `Commentary` node titled
  `Article 28(2)(a): Knowledge`, matching only the token `Knowledge`.
- Query `Article 28` returned zero rows. Provision numbers are not an index
  key; use the node path or body keywords.
- Sampled queries land in different trees: `Akayesu` in `CaseLaw`,
  `command responsibility` in `Lectures`, `specific genocidal intent` in
  `ElementsOfCrimeDigest`.

## Scope limits

- This API covers the Lexsitus platform only. It does not search
  `casematrixnetwork.org` pages, CILRAP news, `toaep.org` catalogues, or the
  whole Legal Tools Database.
- Coverage completeness per tree is not established. A zero hit is a zero hit
  in this index, not proof that Lexsitus or the underlying source lacks the
  material.
- Commentary is secondary material. Cite it as research commentary and verify
  its authorities against the primary text.
