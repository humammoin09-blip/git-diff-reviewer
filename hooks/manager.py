"""
hooks/manager.py - Git Pre-commit Hook Installation and Management for git-diff-reviewer
"""

import sys
import os
import stat
import shutil
from typing import Tuple, Optional


def generate_hook_script(python_path: Optional[str] = None) -> str:
    """
    Generate the pre-commit hook script using the specified or current python interpreter
    path and the 'py' Windows launcher to avoid Windows Store stub aliases.
    """
    py_exec = (python_path or sys.executable).replace("\\", "/")

    return f"""#!/bin/sh
# ==========================================================
# git-diff-reviewer automated pre-commit hook
# ==========================================================

# Resolve Python interpreter (prioritizing current Python executable and 'py' launcher)
CONFIGURED_PYTHON="{py_exec}"

if [ -x "$CONFIGURED_PYTHON" ] || command -v "$CONFIGURED_PYTHON" >/dev/null 2>&1; then
    PYTHON_BIN="$CONFIGURED_PYTHON"
elif command -v py >/dev/null 2>&1; then
    PYTHON_BIN="py"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[git-diff-reviewer] Python executable not found. Skipping automated review."
    exit 0
fi

# Find root of git repository
GIT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$GIT_ROOT" ]; then
    exit 0
fi

MAIN_SCRIPT="$GIT_ROOT/main.py"

if [ ! -f "$MAIN_SCRIPT" ]; then
    echo "[git-diff-reviewer] main.py not found at $MAIN_SCRIPT. Skipping automated review."
    exit 0
fi

echo ""
echo "=========================================================="
echo " [git-diff-reviewer] Running pre-commit AI code review... "
echo "=========================================================="

# Execute reviewer on staged changes
"$PYTHON_BIN" "$MAIN_SCRIPT" --staged

# Exit with code 0 to allow commit to proceed
exit 0
"""


HOOK_SCRIPT_TEMPLATE = generate_hook_script()


def find_git_hooks_dir(repo_dir: Optional[str] = None) -> Optional[str]:
    """
    Locate the .git/hooks directory for the target or current repository.
    """
    base_dir = os.path.abspath(repo_dir or os.getcwd())
    
    # Check if base_dir itself has .git
    git_dir = os.path.join(base_dir, ".git")
    if os.path.isdir(git_dir):
        return os.path.join(git_dir, "hooks")
    
    # Check if base_dir is inside a git repo by walking up
    curr = base_dir
    while True:
        candidate = os.path.join(curr, ".git")
        if os.path.isdir(candidate):
            return os.path.join(candidate, "hooks")
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent

    return None


def is_hook_installed(repo_dir: Optional[str] = None) -> bool:
    """
    Check if the git-diff-reviewer pre-commit hook is installed.
    """
    hooks_dir = find_git_hooks_dir(repo_dir)
    if not hooks_dir:
        return False
    hook_path = os.path.join(hooks_dir, "pre-commit")
    if not os.path.isfile(hook_path):
        return False
    try:
        with open(hook_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            return "git-diff-reviewer" in content
    except Exception:
        return False


def install_pre_commit_hook(
    repo_dir: Optional[str] = None,
    force: bool = False,
    python_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Install the pre-commit hook script into .git/hooks/pre-commit.

    :param repo_dir: Path to the git repository root.
    :param force: If True, overwrites existing hooks.
    :param python_path: Custom Python executable path.
    :return: Tuple of (success_boolean, message)
    """
    hooks_dir = find_git_hooks_dir(repo_dir)
    if not hooks_dir:
        return False, "Not a git repository. Unable to locate .git/hooks directory."

    os.makedirs(hooks_dir, exist_ok=True)
    hook_path = os.path.join(hooks_dir, "pre-commit")

    msg_prefix = ""

    # Check if hook already exists
    if os.path.isfile(hook_path):
        with open(hook_path, "r", encoding="utf-8", errors="replace") as f:
            existing_content = f.read()

        if "git-diff-reviewer" in existing_content and not force:
            # Overwrite to update the template if it's our hook
            pass
        elif not force:
            # Create a backup of the existing foreign hook
            backup_path = hook_path + ".backup"
            shutil.copy2(hook_path, backup_path)
            msg_prefix = f"Existing pre-commit hook backed up to {backup_path}. "
        else:
            msg_prefix = ""

    # Generate hook script with configured Python
    hook_content = generate_hook_script(python_path=python_path)
    normalized_content = hook_content.replace("\r\n", "\n")

    try:
        with open(hook_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(normalized_content)

        # Set executable permissions (0755)
        try:
            current_mode = os.stat(hook_path).st_mode
            os.chmod(hook_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except Exception:
            pass

        return True, f"{msg_prefix}Successfully installed pre-commit hook to: {hook_path}"
    except Exception as e:
        return False, f"Failed to write pre-commit hook: {str(e)}"


def uninstall_pre_commit_hook(repo_dir: Optional[str] = None) -> Tuple[bool, str]:
    """
    Uninstall/remove the git-diff-reviewer pre-commit hook.
    """
    hooks_dir = find_git_hooks_dir(repo_dir)
    if not hooks_dir:
        return False, "Not a git repository. Unable to locate .git/hooks directory."

    hook_path = os.path.join(hooks_dir, "pre-commit")
    backup_path = hook_path + ".backup"

    if not os.path.isfile(hook_path):
        return True, "No pre-commit hook found to uninstall."

    try:
        # Check if there is a backup to restore
        if os.path.isfile(backup_path):
            shutil.copy2(backup_path, hook_path)
            os.remove(backup_path)
            return True, f"Removed git-diff-reviewer hook and restored original backup from: {backup_path}"
        else:
            os.remove(hook_path)
            return True, f"Successfully removed pre-commit hook: {hook_path}"
    except Exception as e:
        return False, f"Failed to uninstall pre-commit hook: {str(e)}"
