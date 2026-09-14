#!/usr/bin/env python3
"""
hooks/install_hook.py - Standalone installer for git-diff-reviewer pre-commit hook
"""
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hooks import install_pre_commit_hook, uninstall_pre_commit_hook


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ["--uninstall", "uninstall", "-u"]:
        success, msg = uninstall_pre_commit_hook()
    else:
        force = "--force" in sys.argv or "-f" in sys.argv
        success, msg = install_pre_commit_hook(force=force)

    print(msg)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
