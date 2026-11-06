"""2.3.2 (TASKS-297): every JS/CSS path `hooks.py` includes exists under `public/`.

`app_include_js` listed `/assets/rnd_warehouse_management/js/warehouse_temperature.js`, a file that is in no commit of
the repository, so every Desk page requested it and got a 404 (measured on prod by Hugh's console, on VPT by Node A).
The `Warehouse` entry of `doctype_js` pointed at the same missing file (read server-side: no 404, but nothing loaded).
DB-free: hooks.py is parsed with `ast` (it is never imported here). Run as `python tests/test_hooks_includes.py`
(a site-packages `tests` package shadows `-m unittest tests.x`).
"""
import ast
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "rnd_warehouse_management")
sys.path.insert(0, ROOT)

ASSET_PREFIX = "/assets/rnd_warehouse_management/"
NAMES = ("app_include_js", "app_include_css", "web_include_js", "web_include_css", "doctype_js", "doctype_list_js")


def hooks():
    tree = ast.parse(open(os.path.join(PKG, "hooks.py"), encoding="utf8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", None) in NAMES:
            out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


def refs():
    """[(hook, key, path-as-written, file-on-disk)] for every include of this app."""
    rows = []
    for name, val in hooks().items():
        items = val.items() if isinstance(val, dict) else [(None, v) for v in val]
        for key, v in items:
            for p in (v if isinstance(v, list) else [v]):
                if p.startswith("/assets/"):
                    if not p.startswith(ASSET_PREFIX):
                        continue                      # another app's asset: not ours to check
                    disk = os.path.join(PKG, "public", p[len(ASSET_PREFIX):])
                else:
                    disk = os.path.join(PKG, p.strip("/"))
                rows.append((name, key, p, disk))
    return rows


class TestEveryIncludeHasAFile(unittest.TestCase):
    def test_the_hooks_declare_includes(self):
        names = {r[0] for r in refs()}
        self.assertTrue({"app_include_js", "app_include_css", "doctype_js", "doctype_list_js"} <= names, names)

    def test_every_included_path_exists_under_public(self):
        missing = [(h, k, p) for h, k, p, disk in refs() if not os.path.isfile(disk)]
        self.assertEqual(missing, [], "hooks.py includes files that do not exist: %s" % missing)

    def test_each_hook_list_individually(self):
        for hook in ("app_include_js", "app_include_css", "doctype_js", "doctype_list_js"):
            for h, k, p, disk in refs():
                if h == hook:
                    self.assertTrue(os.path.isfile(disk), "%s %s -> %s" % (h, k, p))

    def test_the_stale_warehouse_temperature_path_is_gone(self):
        text = open(os.path.join(PKG, "hooks.py"), encoding="utf8").read()
        self.assertNotIn("warehouse_temperature.js", text)

    def test_the_includes_that_work_are_still_there(self):
        h = hooks()
        self.assertEqual(h["app_include_js"], ["/assets/rnd_warehouse_management/js/warehouse_management.js"])
        self.assertEqual(h["app_include_css"], ["/assets/rnd_warehouse_management/css/warehouse_management.css"])
        self.assertEqual(h["doctype_js"], {"Stock Entry": "public/js/stock_entry.js", "Work Order": "public/js/work_order.js"})
        self.assertEqual(h["doctype_list_js"], {"Stock Entry": "public/js/stock_entry_list.js"})


class TestVersion(unittest.TestCase):
    def test_version_is_2_3_2_or_later_in_both_places(self):
        with open(os.path.join(PKG, "__version__.py"), encoding="utf8") as f:
            v1 = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)
        with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf8") as f:
            v2 = re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1)
        self.assertEqual(v1, v2)
        self.assertGreaterEqual(tuple(int(x) for x in v1.split(".")), (2, 3, 2))


if __name__ == "__main__":
    unittest.main()
