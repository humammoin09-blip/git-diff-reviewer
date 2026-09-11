"""
reviewer.py - Git Diff Extraction and Code Review Prompt Construction
"""

import os
import subprocess
from typing import Tuple, Optional, Dict, Any


class GitError(Exception):
    """Exception raised for git-related subprocess failures."""
    pass


def run_git_command(args: list, cwd: Optional[str] = None) -> str:
    """
    Execute a git command using subprocess and return its stdout.
    
    :param args: List of command arguments (e.g. ['git', 'diff']).
    :param cwd: Working directory for git command.
    :return: Stripped string output.
    """
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() or str(e)
        raise GitError(f"Git command '{' '.join(args)}' failed: {error_msg}") from e
    except FileNotFoundError as e:
        raise GitError("Git executable not found. Please ensure Git is installed and in your PATH.") from e


def is_git_repository(cwd: Optional[str] = None) -> bool:
    """Check if the target directory is part of a git repository."""
    try:
        output = run_git_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=cwd)
        return output.lower() == "true"
    except Exception:
        return False


def get_current_branch(cwd: Optional[str] = None) -> str:
    """Get the current git branch name or commit hash."""
    try:
        return run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
    except Exception:
        return "unknown"


def get_git_status_summary(cwd: Optional[str] = None) -> Dict[str, Any]:
    """
    Return a summary of current git working tree status (staged, unstaged, untracked).
    """
    if not is_git_repository(cwd):
        return {"is_git": False}

    branch = get_current_branch(cwd)
    try:
        status_output = run_git_command(["git", "status", "--porcelain"], cwd=cwd)
        staged_count = 0
        unstaged_count = 0
        untracked_count = 0

        for line in status_output.splitlines():
            if len(line) < 2:
                continue
            index_status = line[0]
            worktree_status = line[1]

            if index_status in ["M", "A", "D", "R", "C"]:
                staged_count += 1
            if worktree_status in ["M", "D"]:
                unstaged_count += 1
            if index_status == "?" and worktree_status == "?":
                untracked_count += 1

        return {
            "is_git": True,
            "branch": branch,
            "staged_count": staged_count,
            "unstaged_count": unstaged_count,
            "untracked_count": untracked_count,
        }
    except Exception:
        return {"is_git": True, "branch": branch, "staged_count": 0, "unstaged_count": 0, "untracked_count": 0}


def get_git_diff(
    diff_type: str = "auto",
    target_ref: Optional[str] = None,
    cwd: Optional[str] = None
) -> Tuple[str, str, str]:
    """
    Fetch git diff and diff statistics.

    :param diff_type: 'staged', 'unstaged', 'branch', 'ref', or 'auto'.
    :param target_ref: Specific branch/commit reference to diff against.
    :param cwd: Optional working directory.
    :return: Tuple of (diff_content, diff_stat, detected_type)
    """
    if not is_git_repository(cwd):
        raise GitError("The current directory is not a Git repository.")

    if target_ref or diff_type in ["branch", "ref"]:
        ref = target_ref or "main"
        diff_cmd = ["git", "diff", ref]
        stat_cmd = ["git", "diff", "--stat", ref]
        diff_content = run_git_command(diff_cmd, cwd=cwd)
        diff_stat = run_git_command(stat_cmd, cwd=cwd)
        return diff_content, diff_stat, f"Ref/Branch ({ref})"

    if diff_type == "staged":
        diff_content = run_git_command(["git", "diff", "--cached"], cwd=cwd)
        diff_stat = run_git_command(["git", "diff", "--cached", "--stat"], cwd=cwd)
        return diff_content, diff_stat, "Staged Changes (--cached)"

    if diff_type == "unstaged":
        diff_content = run_git_command(["git", "diff"], cwd=cwd)
        diff_stat = run_git_command(["git", "diff", "--stat"], cwd=cwd)
        return diff_content, diff_stat, "Unstaged Changes"

    # 'auto' mode: check staged first, then unstaged, then last commit
    staged_diff = run_git_command(["git", "diff", "--cached"], cwd=cwd)
    if staged_diff:
        diff_stat = run_git_command(["git", "diff", "--cached", "--stat"], cwd=cwd)
        return staged_diff, diff_stat, "Staged Changes (--cached)"

    unstaged_diff = run_git_command(["git", "diff"], cwd=cwd)
    if unstaged_diff:
        diff_stat = run_git_command(["git", "diff", "--stat"], cwd=cwd)
        return unstaged_diff, diff_stat, "Unstaged Changes"

    # If neither staged nor unstaged, try comparing against HEAD~1 (the latest commit)
    try:
        head_diff = run_git_command(["git", "diff", "HEAD~1"], cwd=cwd)
        if head_diff:
            diff_stat = run_git_command(["git", "diff", "--stat", "HEAD~1"], cwd=cwd)
            return head_diff, diff_stat, "Latest Commit (HEAD~1)"
    except Exception:
        pass

    return "", "", "No Changes Detected"


def truncate_diff(diff_text: str, max_chars: Optional[int] = None) -> str:
    """
    Truncate large diffs to avoid overflowing LLM token context limits.
    """
    if max_chars is None:
        max_chars = int(os.getenv("MAX_DIFF_CHARS", "40000"))

    if len(diff_text) <= max_chars:
        return diff_text

    half_limit = max_chars // 2
    truncated = (
        diff_text[:half_limit]
        + f"\n\n[... Diff truncated ({len(diff_text) - max_chars} characters omitted due to size limit) ...]\n\n"
        + diff_text[-half_limit:]
    )
    return truncated


def build_review_prompt(
    diff_text: str,
    diff_stat: str = "",
    extra_instructions: Optional[str] = None
) -> Tuple[str, str]:
    """
    Construct a strict, high-value code-review prompt.

    :param diff_text: Raw git diff text.
    :param diff_stat: Summary of changed files and line counts.
    :param extra_instructions: Optional additional user instructions.
    :return: Tuple of (system_prompt, user_prompt)
    """
    system_prompt = (
        "You are an expert Principal Software Engineer and Application Security Architect.\n"
        "Your task is to perform an exhaustive, high-rigor, and actionable code review of the provided git diff.\n\n"
        "Focus strictly on the following priority areas:\n"
        "1. CRITICAL BUGS & LOGIC DEFECTS: Off-by-one errors, race conditions, unhandled exceptions, memory/resource leaks, broken invariants.\n"
        "2. SECURITY & SECRETS: Injections (SQL, command, XSS), hardcoded secrets/credentials, insecure deserialization, SSRF, authorization bypass, weak cryptography, unchecked user inputs.\n"
        "3. ERROR HANDLING & RESILIENCE: Missing try/catch or edge cases (null/None/undefined checks, timeouts, network disconnections).\n"
        "4. ANTI-PATTERNS & CODE SMELLS: Code duplication, architectural violations, severe readability/maintainability issues, unnecessary complexity.\n"
        "5. PERFORMANCE CONCERNS: N+1 queries, unindexed queries, blocking I/O on async loops, high algorithmic complexity.\n\n"
        "Formatting and Guidelines:\n"
        "- Format your response using clean GitHub Flavored Markdown.\n"
        "- Structure your review into clear sections:\n"
        "  * **Executive Summary & Verdict**: [APPROVE / REQUEST CHANGES / CRITICAL SECURITY RISK] with a 2-sentence rationale.\n"
        "  * **Key Findings**: Group by severity tag: `[CRITICAL]`, `[WARNING]`, `[SUGGESTION]`, `[PRAISE]`.\n"
        "    - Clearly state the file name and approximate line number(s).\n"
        "    - Explain WHAT the risk/issue is and WHY it matters.\n"
        "    - Provide concise 'Before' and 'After' code snippets showing exactly how to fix the issue.\n"
        "  * **Test & Verification Checklist**: 2-4 concrete tests or edge cases the developer must verify before merging.\n"
        "- If the changes are completely clean and have no issues, praise good practices concisely and issue an APPROVE verdict.\n"
        "- Be precise, objective, and avoid fluff."
    )

    user_prompt_parts = []
    if diff_stat:
        user_prompt_parts.append(f"### Git Diff Stats:\n```text\n{diff_stat}\n```\n")

    if extra_instructions:
        user_prompt_parts.append(f"### Additional Review Instructions:\n{extra_instructions}\n")

    user_prompt_parts.append(f"### Git Diff Under Review:\n```diff\n{diff_text}\n```")

    user_prompt = "\n".join(user_prompt_parts)
    return system_prompt, user_prompt
