import os
import tempfile
import unittest
from hooks import (
    install_pre_commit_hook,
    uninstall_pre_commit_hook,
    is_hook_installed,
    find_git_hooks_dir,
    HOOK_SCRIPT_TEMPLATE,
)


class TestGitHooks(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.repo_dir = self.tmp_dir.name
        self.git_dir = os.path.join(self.repo_dir, ".git")
        os.makedirs(self.git_dir, exist_ok=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_find_git_hooks_dir(self):
        hooks_dir = find_git_hooks_dir(self.repo_dir)
        self.assertIsNotNone(hooks_dir)
        self.assertEqual(os.path.normpath(hooks_dir), os.path.normpath(os.path.join(self.git_dir, "hooks")))

    def test_install_hook(self):
        self.assertFalse(is_hook_installed(self.repo_dir))
        success, msg = install_pre_commit_hook(self.repo_dir)
        self.assertTrue(success)
        self.assertTrue(is_hook_installed(self.repo_dir))

        hook_file = os.path.join(self.git_dir, "hooks", "pre-commit")
        self.assertTrue(os.path.isfile(hook_file))
        with open(hook_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("git-diff-reviewer", content)
            self.assertIn("--staged", content)

    def test_install_hook_with_existing_backup(self):
        hooks_dir = os.path.join(self.git_dir, "hooks")
        os.makedirs(hooks_dir, exist_ok=True)
        hook_file = os.path.join(hooks_dir, "pre-commit")
        with open(hook_file, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho 'custom user hook'\n")

        success, msg = install_pre_commit_hook(self.repo_dir, force=False)
        self.assertTrue(success)

        backup_file = hook_file + ".backup"
        self.assertTrue(os.path.isfile(backup_file))
        with open(backup_file, "r", encoding="utf-8") as f:
            self.assertIn("custom user hook", f.read())

        # Now test uninstall restores backup
        uninst_success, uninst_msg = uninstall_pre_commit_hook(self.repo_dir)
        self.assertTrue(uninst_success)
        self.assertTrue(os.path.isfile(hook_file))
        with open(hook_file, "r", encoding="utf-8") as f:
            self.assertIn("custom user hook", f.read())
        self.assertFalse(os.path.isfile(backup_file))

    def test_uninstall_hook(self):
        install_pre_commit_hook(self.repo_dir)
        self.assertTrue(is_hook_installed(self.repo_dir))

        success, msg = uninstall_pre_commit_hook(self.repo_dir)
        self.assertTrue(success)
        self.assertFalse(is_hook_installed(self.repo_dir))


if __name__ == "__main__":
    unittest.main()
