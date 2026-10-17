"""Offline behavior checks for the Lexsitus adapter."""
import unittest
from types import SimpleNamespace

import lexsitus_search as s


class FakeHTTP:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.evidence = [{"url": "stub", "status": 200}]

    def get_json(self, url, params=None):
        self.calls.append((url, params))
        return self.payload


def hit(tree="Commentary", path="28-a-criminally-responsible", body="<p>Article 28 text</p>"):
    return {
        "id": "node-1",
        "title": "Article 28(1)",
        "path": path,
        "treeKind": tree,
        "parentId": "parent-1",
        "type": "DOCUMENT",
        "description": "description",
        "document": {
            "id": "doc-1",
            "title": "Article 28(1)",
            "richTextDocument": {"body": body} if body else None,
            "pdfDocument": None,
            "videoDocument": None,
        },
    }


def args(**overrides):
    base = dict(query="command responsibility", tree=None, limit=5, offset=0, no_body=False)
    base.update(overrides)
    return SimpleNamespace(**base)


class SearchTests(unittest.TestCase):
    def test_page_and_tree_params(self):
        http = FakeHTTP({"results": [], "pagination": {"total": 0, "page": 3, "limit": 5, "totalPages": 0}})
        s.search(http, args(offset=10, tree="Commentary"))
        url, params = http.calls[0]
        self.assertEqual(url, s.SEARCH_URL)
        self.assertEqual(params, {"query": "command responsibility", "page": 3, "limit": 5, "treeKind": "Commentary"})

    def test_offset_must_be_multiple_of_limit(self):
        with self.assertRaises(ValueError):
            s.search(FakeHTTP({"results": []}), args(offset=3, limit=5))

    def test_unknown_tree_rejected(self):
        with self.assertRaises(ValueError):
            s.search(FakeHTTP({"results": []}), args(tree="Nope"))

    def test_limit_above_ten_rejected(self):
        with self.assertRaises(ValueError):
            s.search(FakeHTTP({"results": []}), args(limit=11))

    def test_commentary_row_has_human_url_and_body(self):
        http = FakeHTTP({"results": [hit()], "pagination": {"total": 1, "page": 1, "limit": 5, "totalPages": 1}})
        out = s.search(http, args())
        row = out["results"][0]
        self.assertEqual(row["url"], s.BASE + "/en/clicc/28-a-criminally-responsible")
        self.assertIn("treeKind=Commentary", row["api_url"])
        self.assertEqual(row["access"], "commentary-text")
        self.assertEqual(row["full_text"], "Article 28 text")

    def test_non_commentary_row_keeps_api_url(self):
        http = FakeHTTP({"results": [hit(tree="CaseLaw", path="b8d7bd", body="")],
                         "pagination": {"total": 1, "page": 1, "limit": 5, "totalPages": 1}})
        row = s.search(http, args())["results"][0]
        self.assertEqual(row["url"], row["api_url"])
        self.assertIn("treeKind=CaseLaw", row["url"])
        self.assertEqual(row["access"], "metadata")

    def test_next_offset_follows_full_page(self):
        full = {"results": [hit(), hit()], "pagination": {"page": 1, "limit": 2}}
        self.assertEqual(s.search(FakeHTTP(full), args(limit=2))["next_offset"], 2)
        short = {"results": [hit()], "pagination": {"page": 3, "limit": 2}}
        self.assertIsNone(s.search(FakeHTTP(short), args(limit=2, offset=4))["next_offset"])

    def test_api_pagination_is_not_reported_as_exact(self):
        payload = {"results": [hit()], "pagination": {"total": 30, "page": 1, "limit": 5, "totalPages": 6}}
        out = s.search(FakeHTTP(payload), args())
        self.assertNotIn("total", out)
        self.assertEqual(out["api_total"], 30)
        self.assertFalse(out["api_pagination_reliable"])

    def test_blank_title_falls_back_to_body(self):
        row = hit()
        row["title"] = " "
        row["document"]["title"] = " "
        http = FakeHTTP({"results": [row], "pagination": {"page": 1, "limit": 5}})
        self.assertEqual(s.search(http, args())["results"][0]["title"], "Article 28 text")

    def test_no_body_omits_full_text(self):
        http = FakeHTTP({"results": [hit()], "pagination": {"total": 1, "page": 1, "limit": 5, "totalPages": 1}})
        row = s.search(http, args(no_body=True))["results"][0]
        self.assertNotIn("full_text", row)
        self.assertNotIn("body_html", row)
        self.assertTrue(row["snippet"])


class FetchTests(unittest.TestCase):
    def test_bare_path_defaults_to_commentary(self):
        url = s.node_url_for("28-a-criminally-responsible", None)
        self.assertEqual(url, s.NODE_URL.format(path="28-a-criminally-responsible", tree="Commentary"))

    def test_clicc_page_url_is_converted_to_node_api(self):
        url = s.node_url_for("https://cilrap-lexsitus.org/en/clicc/28-a-criminally-responsible", None)
        self.assertIn("/api/v1/nodes/path/28-a-criminally-responsible", url)
        self.assertIn("treeKind=Commentary", url)

    def test_api_url_passes_through(self):
        target = s.NODE_URL.format(path="b8d7bd", tree="CaseLaw")
        self.assertEqual(s.node_url_for(target, None), target)

    def test_foreign_host_rejected(self):
        with self.assertRaises(ValueError):
            s.node_url_for("https://example.com/api/v1/nodes/path/x", None)

    def test_fetch_extracts_text_and_metadata(self):
        payload = {"title": "Article 28(1)", "path": "28-a", "treeKind": "Commentary", "type": "DOCUMENT",
                   "updatedAt": "2026-08-27T11:12:22.269Z",
                   "document": {"richTextDocument": {"body": "<p>shall be <em>criminally responsible</em></p>"},
                                "pdfDocument": None, "videoDocument": None}}
        out = s.fetch(FakeHTTP(payload), SimpleNamespace(target="28-a", tree=None, text_out=None))
        self.assertEqual(out["text"], "shall be criminally responsible")
        self.assertEqual(out["text_characters"], len(out["text"]))
        self.assertEqual(out["tree_kind"], "Commentary")


class TreeTests(unittest.TestCase):
    def test_static_tree_list_without_query(self):
        out = s.trees(None, None)
        names = [row["tree_kind"] for row in out["trees"]]
        self.assertIn("Commentary", names)
        self.assertIn("CaseLaw", names)
        self.assertEqual(len(names), len(s.TREES))
        self.assertFalse(any("total" in row for row in out["trees"]))

    def test_query_probe_pages_until_short_page(self):
        class PagingHTTP:
            def __init__(self):
                self.calls = []
                self.evidence = []

            def get_json(self, url, params=None):
                self.calls.append(params)
                count = 10 if params["page"] == 1 else 0
                return {"results": [hit() for _ in range(count)]}

        http = PagingHTTP()
        out = s.trees(http, "genocide")
        self.assertEqual(len(http.calls), len(s.TREES) * 2)
        self.assertTrue(all(row["counted"] == 10 for row in out["trees"]))
        self.assertFalse(any(row["count_is_lower_bound"] for row in out["trees"]))
        self.assertTrue(all(row["count_is_reliable"] is False for row in out["trees"]))

    def test_query_probe_marks_lower_bound_at_cap(self):
        class FullHTTP:
            evidence = []

            def get_json(self, url, params=None):
                return {"results": [hit() for _ in range(10)]}

        out = s.trees(FullHTTP(), "genocide", max_pages=1)
        self.assertTrue(all(row["counted"] == 10 for row in out["trees"]))
        self.assertTrue(all(row["count_is_lower_bound"] for row in out["trees"]))


if __name__ == "__main__":
    unittest.main()
