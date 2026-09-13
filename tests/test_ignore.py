import os
import tempfile
import unittest
from ignore import (
    load_ignore_patterns,
    matches_pattern,
    is_ignored,
    split_diff_into_files,
    filter_diff,
    DEFAULT_IGNORE_PATTERNS,
)


class TestIgnore(unittest.TestCase):

    def test_default_patterns_loaded_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            patterns = load_ignore_patterns(root_dir=tmpdir)
            self.assertEqual(patterns, list(DEFAULT_IGNORE_PATTERNS))
            self.assertIn("package-lock.json", patterns)
            self.assertIn("*.lock", patterns)
            self.assertIn("node_modules/", patterns)

    def test_custom_reviewerignore_file_loaded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ignore_path = os.path.join(tmpdir, ".reviewerignore")
            with open(ignore_path, "w", encoding="utf-8") as f:
                f.write("# Comment\n\ncustom_file.txt\n*.temp\nbuild_out/\n")

            patterns = load_ignore_patterns(root_dir=tmpdir)
            self.assertEqual(patterns, ["custom_file.txt", "*.temp", "build_out/"])

    def test_matches_pattern_lockfiles(self):
        patterns = ["package-lock.json", "*.lock", "pnpm-lock.yaml"]
        self.assertTrue(is_ignored("package-lock.json", patterns))
        self.assertTrue(is_ignored("frontend/package-lock.json", patterns))
        self.assertTrue(is_ignored("yarn.lock", patterns))
        self.assertTrue(is_ignored("backend/Cargo.lock", patterns))
        self.assertTrue(is_ignored("pnpm-lock.yaml", patterns))
        self.assertFalse(is_ignored("src/lock_service.py", patterns))

    def test_matches_pattern_directories(self):
        patterns = ["dist/", "node_modules/", "build/"]
        self.assertTrue(is_ignored("dist/bundle.js", patterns))
        self.assertTrue(is_ignored("client/dist/bundle.js", patterns))
        self.assertTrue(is_ignored("node_modules/express/index.js", patterns))
        self.assertTrue(is_ignored("build/output.bin", patterns))
        self.assertFalse(is_ignored("src/distribution.py", patterns))
        self.assertFalse(is_ignored("builder/script.py", patterns))

    def test_matches_pattern_env_and_minified(self):
        patterns = [".env", ".env.*", "*.min.js"]
        self.assertTrue(is_ignored(".env", patterns))
        self.assertTrue(is_ignored(".env.local", patterns))
        self.assertTrue(is_ignored("config/.env.production", patterns))
        self.assertTrue(is_ignored("static/app.min.js", patterns))
        self.assertFalse(is_ignored("src/environment.py", patterns))
        self.assertFalse(is_ignored("static/app.js", patterns))

    def test_filter_diff_removes_ignored_files(self):
        diff_text = """diff --git a/package-lock.json b/package-lock.json
index 1111111..2222222 100644
--- a/package-lock.json
+++ b/package-lock.json
@@ -1,3 +1,3 @@
-"version": "1.0.0"
+"version": "1.0.1"
diff --git a/src/app.py b/src/app.py
index 3333333..4444444 100644
--- a/src/app.py
+++ b/src/app.py
@@ -10,2 +10,3 @@
 def run():
+    print("Secure run")
"""
        diff_stat = """package-lock.json | 2 +-
src/app.py        | 1 +
2 files changed, 2 insertions(+), 1 deletion(-)"""

        filtered_diff, filtered_stat, ignored_files = filter_diff(
            diff_text, diff_stat, patterns=["package-lock.json"]
        )

        self.assertIn("package-lock.json", ignored_files)
        self.assertNotIn("package-lock.json", filtered_diff)
        self.assertIn("src/app.py", filtered_diff)
        self.assertIn("print(\"Secure run\")", filtered_diff)
        self.assertNotIn("package-lock.json", filtered_stat)
        self.assertIn("src/app.py", filtered_stat)

    def test_filter_diff_all_ignored(self):
        diff_text = """diff --git a/yarn.lock b/yarn.lock
index 1111111..2222222 100644
--- a/yarn.lock
+++ b/yarn.lock
@@ -1 +1 @@
-old
+new
"""
        filtered_diff, filtered_stat, ignored = filter_diff(
            diff_text, patterns=["*.lock"]
        )
        self.assertEqual(filtered_diff, "")
        self.assertEqual(ignored, ["yarn.lock"])


if __name__ == "__main__":
    unittest.main()
