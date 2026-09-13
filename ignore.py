"""
ignore.py - Ignore pattern matching and diff filtering for .reviewerignore
"""

import os
import re
import fnmatch
from typing import List, Optional, Tuple, Dict, Any


DEFAULT_IGNORE_PATTERNS = [
    # Package manager lockfiles
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "composer.lock",
    "Cargo.lock",
    "poetry.lock",
    "Pipfile.lock",
    "Gemfile.lock",
    "mix.lock",
    "flake.lock",
    "*.lock",

    # Dependencies & virtual environments
    "node_modules/",
    ".venv/",
    "venv/",
    "env/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.egg-info/",

    # Build outputs & distributions
    "dist/",
    "build/",
    "target/",
    "out/",
    "vendor/",
    "bundle/",

    # Environment variables & secrets
    ".env",
    ".env.*",
    "*.env",

    # Minified assets & source maps
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.bundle.js",

    # Binary, media, and document formats
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.svg",
    "*.ico",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
]

REVIEWER_IGNORE_FILENAME = ".reviewerignore"


def load_ignore_patterns(root_dir: Optional[str] = None) -> List[str]:
    """
    Load ignore patterns from root-level .reviewerignore if present.
    If the file does not exist, return DEFAULT_IGNORE_PATTERNS.

    :param root_dir: Directory where .reviewerignore is expected (defaults to cwd).
    :return: List of pattern strings.
    """
    base_dir = root_dir or os.getcwd()
    ignore_file_path = os.path.join(base_dir, REVIEWER_IGNORE_FILENAME)

    if os.path.isfile(ignore_file_path):
        try:
            patterns = []
            with open(ignore_file_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
            if patterns:
                return patterns
        except Exception:
            pass

    return list(DEFAULT_IGNORE_PATTERNS)


def normalize_path(path: str) -> str:
    """Normalize file path to POSIX style without leading/trailing slashes."""
    p = path.replace("\\", "/").strip()
    p = p.removeprefix("./").removeprefix("/")
    return p


def matches_pattern(path: str, pattern: str) -> bool:
    """
    Check if a given path matches an ignore pattern.

    :param path: Relative or normalized file path.
    :param pattern: Ignore pattern (e.g. '*.lock', 'dist/', 'node_modules/').
    :return: True if path matches the pattern, False otherwise.
    """
    norm_path = normalize_path(path)
    pattern = pattern.replace("\\", "/").strip()

    if not norm_path or not pattern:
        return False

    is_dir_pattern = pattern.endswith("/")
    clean_pattern = pattern.rstrip("/")

    parts = norm_path.split("/")
    filename = parts[-1]

    # 1. Directory pattern matching (e.g. 'dist/', 'node_modules/')
    if is_dir_pattern or "/" not in pattern:
        # Check any directory segment
        for part in parts[:-1]:
            if fnmatch.fnmatch(part, clean_pattern):
                return True
        # If directory pattern, match first segment if path is within it
        if is_dir_pattern and parts and fnmatch.fnmatch(parts[0], clean_pattern):
            return True

    # 2. Match basename directly (e.g. 'package-lock.json', '*.lock')
    if fnmatch.fnmatch(filename, clean_pattern):
        return True

    # 3. Match entire path
    if fnmatch.fnmatch(norm_path, clean_pattern):
        return True

    # 4. Match prefix / suffix wildcards (e.g. 'dist/*', '*/dist/*')
    if fnmatch.fnmatch(norm_path, f"*/{clean_pattern}") or fnmatch.fnmatch(norm_path, f"{clean_pattern}/*"):
        return True

    # 5. Relative match
    clean_no_slash = clean_pattern.lstrip("/")
    if fnmatch.fnmatch(norm_path, clean_no_slash) or fnmatch.fnmatch(norm_path, f"*/{clean_no_slash}"):
        return True

    return False


def is_ignored(path: str, patterns: List[str]) -> bool:
    """
    Check if a path matches any pattern in the list.
    """
    if not path:
        return False
    for pat in patterns:
        if matches_pattern(path, pat):
            return True
    return False


def extract_file_paths_from_diff_header(header_line: str) -> Tuple[str, str]:
    """Extract (old_path, new_path) from 'diff --git ...' header."""
    header = header_line.strip()
    if not header.startswith("diff --git "):
        return "", ""
    rest = header[len("diff --git "):].strip()

    match = re.match(r'^(?:"a/(.*?)"|a/(.*?))\s+(?:"b/(.*?)"|b/(.*?))$', rest)
    if match:
        old_p = match.group(1) or match.group(2) or ""
        new_p = match.group(3) or match.group(4) or ""
        return old_p, new_p

    if " b/" in rest:
        parts = rest.split(" b/", 1)
        old_p = parts[0].removeprefix("a/").strip('"')
        new_p = parts[1].strip('"')
        return old_p, new_p

    return "", ""


def split_diff_into_files(diff_text: str) -> List[Dict[str, Any]]:
    """
    Split a unified git diff into individual file diff blocks.
    """
    if not diff_text or not diff_text.strip():
        return []

    lines = diff_text.splitlines(keepends=True)
    file_chunks = []
    current_chunk_lines = []
    current_header = ""

    for line in lines:
        if line.startswith("diff --git "):
            if current_chunk_lines:
                chunk_str = "".join(current_chunk_lines)
                old_p, new_p = extract_file_paths_from_diff_header(current_header)
                file_chunks.append({
                    "header": current_header,
                    "old_path": old_p,
                    "new_path": new_p,
                    "content": chunk_str,
                })
                current_chunk_lines = []
            current_header = line.strip()
        current_chunk_lines.append(line)

    if current_chunk_lines:
        chunk_str = "".join(current_chunk_lines)
        old_p, new_p = extract_file_paths_from_diff_header(current_header)
        file_chunks.append({
            "header": current_header,
            "old_path": old_p,
            "new_path": new_p,
            "content": chunk_str,
        })

    return file_chunks


def filter_diff(
    diff_content: str,
    diff_stat: str = "",
    patterns: Optional[List[str]] = None,
    cwd: Optional[str] = None
) -> Tuple[str, str, List[str]]:
    """
    Filter out files matching ignore patterns from git diff and git diff stat.

    :param diff_content: Raw git diff text.
    :param diff_stat: Raw git diff stat text.
    :param patterns: Optional list of ignore patterns. If None, loaded from .reviewerignore or defaults.
    :param cwd: Working directory for loading .reviewerignore.
    :return: Tuple of (filtered_diff_content, filtered_diff_stat, ignored_files_list)
    """
    if patterns is None:
        patterns = load_ignore_patterns(root_dir=cwd)

    if not diff_content or not diff_content.strip():
        return diff_content, diff_stat, []

    chunks = split_diff_into_files(diff_content)
    if not chunks:
        return diff_content, diff_stat, []

    kept_chunks = []
    ignored_files = []

    for chunk in chunks:
        old_path = chunk["old_path"]
        new_path = chunk["new_path"]

        target_path = new_path if (new_path and new_path != "/dev/null") else old_path

        if is_ignored(target_path, patterns) or (old_path and is_ignored(old_path, patterns)):
            ignored_files.append(target_path)
        else:
            kept_chunks.append(chunk["content"])

    filtered_diff = "".join(kept_chunks).strip()

    # Filter diff_stat lines corresponding to ignored files
    filtered_stat = ""
    if diff_stat:
        stat_lines = diff_stat.splitlines()
        filtered_lines = []
        for line in stat_lines:
            line_ignored = False
            for ignored_f in ignored_files:
                clean_line = line.strip()
                if clean_line.startswith(ignored_f) or f" {ignored_f} " in line or f" {ignored_f}|" in line:
                    line_ignored = True
                    break
            if not line_ignored and "|" in line:
                file_part = line.split("|")[0].strip()
                if "=>" in file_part:
                    file_part = file_part.split("=>")[-1].strip()
                if is_ignored(file_part, patterns):
                    line_ignored = True
            if not line_ignored:
                filtered_lines.append(line)
        filtered_stat = "\n".join(filtered_lines).strip()

    return filtered_diff, filtered_stat, ignored_files
