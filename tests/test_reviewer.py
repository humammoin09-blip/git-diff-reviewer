import unittest
import os
from reviewer import truncate_diff, build_review_prompt, is_git_repository


class TestReviewer(unittest.TestCase):
    def test_truncate_diff_small(self):
        diff = "diff --git a/test.py b/test.py\n+print('hello')"
        result = truncate_diff(diff, max_chars=100)
        self.assertEqual(result, diff)

    def test_truncate_diff_large(self):
        large_diff = "A" * 200
        result = truncate_diff(large_diff, max_chars=50)
        self.assertIn("[... Diff truncated", result)
        self.assertEqual(len(result[:25]), 25)
        self.assertEqual(len(result[-25:]), 25)

    def test_build_review_prompt(self):
        diff = "diff --git a/app.py b/app.py\n+password = '12345'"
        stat = "app.py | 1 +"
        instructions = "Check hardcoded secrets"
        system_prompt, user_prompt = build_review_prompt(
            diff_text=diff,
            diff_stat=stat,
            extra_instructions=instructions
        )
        self.assertIn("Principal Software Engineer", system_prompt)
        self.assertIn("CRITICAL BUGS", system_prompt)
        self.assertIn("Check hardcoded secrets", user_prompt)
        self.assertIn(diff, user_prompt)
        self.assertIn(stat, user_prompt)

    def test_is_git_repository(self):
        # The workspace root or test environment should be verified
        res = is_git_repository()
        self.assertIsInstance(res, bool)


if __name__ == "__main__":
    unittest.main()
