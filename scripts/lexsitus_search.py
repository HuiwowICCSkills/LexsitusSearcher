"""Standalone Lexsitus retrieval over the CILRAP public API.

Search the Lexsitus content trees, read one node by path, and report exactly
which API route and response were used. No login or browser is involved.
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://cilrap-lexsitus.org"
SEARCH_URL = BASE + "/api/v1/search"
NODE_URL = BASE + "/api/v1/nodes/path/{path}?treeKind={tree}&lang=en"
CLICC_URL = BASE + "/en/clicc/{path}"
UA = "LexsitusSearcher/1.0 (public legal research; direct HTTP)"
NOW = lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

# Observed on the public API. Commentary is the only tree whose human reading
# route has been verified; the others keep their API node URL.
TREES = {
    "Commentary": "CLICC commentary on Rome Statute provisions",
    "RPECommentary": "Commentary on the Rules of Procedure and Evidence",
    "CaseLaw": "Case-law records mapped to Legal Tools identifiers",
    "RomeStatute": "Rome Statute provision nodes",
    "ElementsOfCrime": "Elements of Crimes",
    "ElementsOfCrimeDigest": "Elements of Crimes digest",
    "MeansOfProofDigest": "Means of proof digest",
    "PreparatoryWork": "Preparatory works",
    "TOAEP": "TOAEP publications hosted in Lexsitus",
    "Lectures": "Video lectures and transcripts",
}


class AccessError(RuntimeError):
    pass


def clean(value: str) -> str:
    value = str(value or "")
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True) if "<" in value else html_lib.unescape(value)


def snippet(value: str, width: int = 600) -> str:
    text = clean(value)
    return text[:width] + ("…" if len(text) > width else "")


class HTTP:
    def __init__(self, cache: Path, ttl: int = 86400, offline: bool = False):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl
        self.offline = offline
        self.evidence: list[dict] = []
        self.last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA

    def get_json(self, url: str, params: dict | None = None):
        prepared = requests.Request("GET", url, params=params).prepare()
        identity = prepared.url
        key = hashlib.sha256(identity.encode()).hexdigest()
        body_path, meta_path = self.cache / (key + ".bin"), self.cache / (key + ".json")
        if body_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if self.offline or time.time() - meta_path.stat().st_mtime < self.ttl:
                self.evidence.append({**meta, "cached": True})
                return json.loads(body_path.read_bytes())
        if self.offline:
            raise AccessError("offline cache miss: " + prepared.url)
        time.sleep(max(0.0, 0.4 - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        with self.session.get(url, params=params, timeout=(12, 45), stream=True) as response:
            meta = {
                "url": response.url,
                "status": response.status_code,
                "content_type": response.headers.get("Content-Type", ""),
                "retrieved_at": NOW(),
            }
            self.evidence.append(meta)
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 40 * 1024 * 1024:
                    raise AccessError("40 MiB response limit: " + response.url)
                chunks.append(chunk)
            body = b"".join(chunks)
            meta["sha256"] = hashlib.sha256(body).hexdigest()
            if not response.ok:
                detail = clean(body.decode("utf-8", "replace"))[:300]
                raise AccessError(f"HTTP {response.status_code}: {response.url} {detail}".strip())
            if "json" not in meta["content_type"]:
                raise AccessError("expected JSON from " + response.url)
            body_path.write_bytes(body)
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            return json.loads(body)


def search_rows(payload: dict, query: str, include_body: bool = True) -> list[dict]:
    rows = []
    for hit in payload.get("results", []):
        document = hit.get("document") or {}
        rich = document.get("richTextDocument") or {}
        pdf = document.get("pdfDocument") or {}
        video = document.get("videoDocument") or {}
        tree = hit.get("treeKind") or ""
        path = hit.get("path") or ""
        api_url = NODE_URL.format(path=quote(path, safe=""), tree=quote(tree))
        url = CLICC_URL.format(path=path) if tree == "Commentary" else api_url
        body = rich.get("body") or ""
        body_text = clean(body)
        title = (hit.get("title") or "").strip() or (document.get("title") or "").strip()
        if not title:
            title = (body_text[:80] + ("…" if len(body_text) > 80 else "")) if body_text else "(untitled: " + path + ")"
        row = {
            "id": hit.get("id"),
            "title": title,
            "path": path,
            "tree_kind": tree,
            "type": hit.get("type"),
            "url": url,
            "api_url": api_url,
            "parent_id": hit.get("parentId"),
            "snippet": snippet(body or hit.get("description") or ""),
            "access": "commentary-text" if body else "metadata",
            "pdf_url": pdf.get("pdfUrl"),
            "video_url": video.get("videoUrl"),
        }
        if include_body and body:
            row["body_html"] = body
            row["full_text"] = body_text
        rows.append(row)
    return rows


def search(http: HTTP, args) -> dict:
    if args.limit < 1 or args.limit > 50:
        raise ValueError("--limit must be 1..50")
    if args.offset < 0:
        raise ValueError("--offset must be >= 0")
    if args.offset % args.limit:
        raise ValueError("--offset must be a multiple of --limit (the API is page-based)")
    if args.tree and args.tree not in TREES:
        raise ValueError("unknown --tree; run the trees command")
    page = args.offset // args.limit + 1
    params = {"query": args.query, "page": page, "limit": args.limit}
    if args.tree:
        params["treeKind"] = args.tree
    payload = http.get_json(SEARCH_URL, params)
    pagination = payload.get("pagination") or {}
    rows = search_rows(payload, args.query, include_body=not args.no_body)
    consumed = args.offset + len(rows)
    return {
        "query": args.query,
        "tree": args.tree or "all trees",
        "status": "ok",
        "page": pagination.get("page", page),
        "limit": args.limit,
        # next_offset advances only while the API returns a full page. The
        # backend does not fill the last page, so a short page marks the end.
        "next_offset": consumed if len(rows) == args.limit else None,
        "api_total": pagination.get("total"),
        "api_total_pages": pagination.get("totalPages"),
        "api_pagination_reliable": False,
        "pagination_warning": (
            "The API's pagination.total/totalPages are inconsistent with the rows it returns "
            "(observed 2026-10-18: total=30 while pages 1-4 held 40 rows). Page through with "
            "next_offset and stop on an empty or short page; do not quote api_total as an exact hit count."
        ),
        "results": rows,
        "scope": (
            "Lexsitus platform search (cilrap-lexsitus.org). Without --tree the API mixes all "
            "content trees. Matching is term-based; provision numbers are not indexed."
        ),
        "evidence": http.evidence,
        "retrieved_at": NOW(),
    }


def node_url_for(target: str, tree: str | None) -> str:
    parsed = urlparse(target)
    if parsed.scheme in ("http", "https"):
        host = (parsed.hostname or "").lower()
        if host != "cilrap-lexsitus.org":
            raise ValueError("only cilrap-lexsitus.org URLs or bare node paths are accepted")
        if "/api/v1/nodes/path/" in parsed.path:
            return target
        if parsed.path.startswith("/en/clicc/"):
            path = parsed.path[len("/en/clicc/"):].strip("/")
            return NODE_URL.format(path=quote(path, safe=""), tree="Commentary")
        raise ValueError("URL must be an API node route or a /en/clicc/<path> page")
    path = target.strip("/")
    if not path:
        raise ValueError("empty node path")
    return NODE_URL.format(path=quote(path, safe=""), tree=quote(tree or "Commentary"))


def fetch(http: HTTP, args) -> dict:
    url = node_url_for(args.target, args.tree)
    data = http.get_json(url)
    document = data.get("document") or {}
    rich = document.get("richTextDocument") or {}
    pdf = document.get("pdfDocument") or {}
    video = document.get("videoDocument") or {}
    body = rich.get("body") or ""
    text = clean(body)
    out = {
        "url": url,
        "title": data.get("title") or document.get("title") or "",
        "path": data.get("path") or document.get("path") or "",
        "tree_kind": data.get("treeKind") or document.get("type") or "",
        "type": data.get("type"),
        "updated_at": data.get("updatedAt"),
        "text": text,
        "text_characters": len(text),
        "pdf_url": pdf.get("pdfUrl"),
        "video_url": video.get("videoUrl"),
        "data": data,
        "evidence": http.evidence,
        "retrieved_at": NOW(),
    }
    if body:
        out["body_html"] = body
    if args.text_out:
        Path(args.text_out).write_text(text + "\n", encoding="utf-8")
    return out


def trees(http: HTTP | None, query: str | None, max_pages: int = 4) -> dict:
    rows = [{"tree_kind": name, "description": desc} for name, desc in TREES.items()]
    if query and http:
        for row in rows:
            counted, page = 0, 1
            while page <= max_pages:
                payload = http.get_json(
                    SEARCH_URL,
                    {"query": query, "page": page, "limit": 50, "treeKind": row["tree_kind"]},
                )
                results = payload.get("results") or []
                counted += len(results)
                if len(results) < 50:
                    break
                page += 1
            row["counted"] = counted
            row["count_is_lower_bound"] = page > max_pages
    return {
        "trees": rows,
        "query": query,
        "note": (
            "Counts page through the API until a short page; they are query-specific and "
            "lower bounds when --max-pages was reached. They are not tree sizes."
        ),
        "evidence": http.evidence if http else [],
        "retrieved_at": NOW(),
    }


def doctor(args) -> dict:
    started = time.monotonic()
    http = HTTP(Path(args.cache), args.cache_ttl, args.offline)
    payload = http.get_json(SEARCH_URL, {"query": "genocide", "page": 1, "limit": 1})
    return {
        "status": "ok",
        "api": SEARCH_URL,
        "http_status": http.evidence[-1]["status"] if http.evidence else None,
        "total_for_genocide": (payload.get("pagination") or {}).get("total"),
        "latency_ms": round((time.monotonic() - started) * 1000),
        "python_requests": requests.__version__,
        "evidence": http.evidence,
        "retrieved_at": NOW(),
    }


def emit(out: dict, path: str | None):
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if path:
        Path(path).write_text(text + "\n", encoding="utf-8")
        print(path)
    else:
        print(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    search_parser = sub.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--tree")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--offset", type=int, default=0)
    search_parser.add_argument("--no-body", action="store_true", help="keep snippets only, omit body_html/full_text")

    fetch_parser = sub.add_parser("fetch")
    fetch_parser.add_argument("target", help="bare node path, API node URL, or /en/clicc/<path> page")
    fetch_parser.add_argument("--tree", default=None, help="tree kind for a bare path (default Commentary)")
    fetch_parser.add_argument("--text-out")

    trees_parser = sub.add_parser("trees")
    trees_parser.add_argument("--query", help="also report per-tree hit counts for this query")
    trees_parser.add_argument("--max-pages", type=int, default=4, help="count-probe page cap per tree")
    sub.add_parser("doctor")

    for item in (search_parser, fetch_parser, trees_parser, sub.choices["doctor"]):
        item.add_argument("--cache", default=str(Path.cwd() / ".lexsitus-cache"))
        item.add_argument("--cache-ttl", type=int, default=86400)
        item.add_argument("--offline", action="store_true")
        item.add_argument("--out")

    args = parser.parse_args()
    try:
        if args.command == "doctor":
            out = doctor(args)
        else:
            http = HTTP(Path(args.cache), args.cache_ttl, args.offline)
            if args.command == "search":
                out = search(http, args)
            elif args.command == "fetch":
                out = fetch(http, args)
            else:
                out = trees(http if args.query else None, args.query, args.max_pages)
        emit(out, getattr(args, "out", None))
        return 0
    except (AccessError, ValueError, KeyError, TypeError) as exc:
        emit({"status": "error", "error": str(exc), "retrieved_at": NOW()}, getattr(args, "out", None))
        return 1


if __name__ == "__main__":
    sys.exit(main())
