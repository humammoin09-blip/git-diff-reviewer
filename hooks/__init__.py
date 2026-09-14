"""Pre-commit Git Hook automation package."""
from hooks.manager import (
    install_pre_commit_hook,
    uninstall_pre_commit_hook,
    is_hook_installed,
    find_git_hooks_dir,
    generate_hook_script,
    HOOK_SCRIPT_TEMPLATE,
)

__all__ = [
    "install_pre_commit_hook",
    "uninstall_pre_commit_hook",
    "is_hook_installed",
    "find_git_hooks_dir",
    "generate_hook_script",
    "HOOK_SCRIPT_TEMPLATE",
]
