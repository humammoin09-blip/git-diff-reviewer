"""
main.py - Git Diff Reviewer CLI Entrypoint

Interactive CLI tool that inspects local git diffs and sends them to configured
LLM providers (OpenRouter, Gemini, Groq, Ollama) for automated code review.
"""

import sys
import os
import argparse
from typing import Optional

# Import local modules
from llm import get_llm_provider, LLMError, LLMConfigurationError, LLMProviderError, PROVIDERS
from reviewer import (
    is_git_repository,
    get_git_status_summary,
    get_git_diff,
    truncate_diff,
    build_review_prompt,
    load_ignore_patterns,
    GitError,
)

# Optional rich formatting support with fallback
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.table import Table
    from rich.status import Status
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


def print_info(text: str):
    """Print informative message."""
    if RICH_AVAILABLE:
        console.print(f"[bold cyan]ℹ[/bold cyan] {text}")
    else:
        print(f"[INFO] {text}")


def print_success(text: str):
    """Print success message."""
    if RICH_AVAILABLE:
        console.print(f"[bold green]✔[/bold green] {text}")
    else:
        print(f"[SUCCESS] {text}")


def print_warning(text: str):
    """Print warning message."""
    if RICH_AVAILABLE:
        console.print(f"[bold yellow]⚠[/bold yellow] {text}")
    else:
        print(f"[WARNING] {text}")


def print_error(text: str):
    """Print error message."""
    if RICH_AVAILABLE:
        console.print(f"[bold red]✖[/bold red] {text}")
    else:
        print(f"[ERROR] {text}")


def render_markdown(md_text: str, raw: bool = False):
    """Render markdown either formatted via Rich or as raw text."""
    if raw or not RICH_AVAILABLE:
        print("\n" + md_text + "\n")
    else:
        console.print("\n")
        console.print(
            Panel(
                Markdown(md_text),
                title="[bold green]AI Code Review Output[/bold green]",
                border_style="green",
                expand=True,
            )
        )


def show_status(provider_override: Optional[str] = None, model_override: Optional[str] = None):
    """Display current git repository status, ignore rules, and LLM configuration."""
    status = get_git_status_summary()
    active_provider = (provider_override or os.getenv("LLM_PROVIDER", "openrouter")).lower()
    active_model = model_override or os.getenv("LLM_MODEL", "(provider default)")
    
    ignore_file_exists = os.path.isfile(".reviewerignore")
    patterns = load_ignore_patterns()
    ignore_desc = f".reviewerignore ({len(patterns)} rules)" if ignore_file_exists else f"Smart Defaults ({len(patterns)} rules)"

    if RICH_AVAILABLE:
        table = Table(title="Git Diff Reviewer - Status Summary", border_style="cyan")
        table.add_column("Property", style="bold white")
        table.add_column("Value", style="cyan")

        table.add_row("Git Repository", "Yes" if status.get("is_git") else "[red]No[/red]")
        if status.get("is_git"):
            table.add_row("Current Branch", status.get("branch", "unknown"))
            table.add_row("Staged Changes", f"{status.get('staged_count', 0)} files")
            table.add_row("Unstaged Changes", f"{status.get('unstaged_count', 0)} files")
            table.add_row("Untracked Files", f"{status.get('untracked_count', 0)} files")
        
        table.add_row("Ignore Rules", f"[bold green]{ignore_desc}[/bold green]")
        table.add_row("Configured Provider", f"[bold yellow]{active_provider}[/bold yellow]")
        table.add_row("Configured Model", active_model)
        console.print(table)
    else:
        print("=== Git Diff Reviewer Status ===")
        print(f"Git Repository: {'Yes' if status.get('is_git') else 'No'}")
        if status.get("is_git"):
            print(f"Current Branch: {status.get('branch', 'unknown')}")
            print(f"Staged Changes: {status.get('staged_count', 0)} files")
            print(f"Unstaged Changes: {status.get('unstaged_count', 0)} files")
            print(f"Untracked Files: {status.get('untracked_count', 0)} files")
        print(f"Ignore Rules: {ignore_desc}")
        print(f"Configured Provider: {active_provider}")
        print(f"Configured Model: {active_model}")
        print("================================")


def interactive_mode() -> dict:
    """Prompt user interactively to select what changes to review."""
    print_info("Interactive Review Setup")
    print("Select diff target:")
    print("  1. Auto-detect (Staged changes first, then unstaged)")
    print("  2. Staged changes only (--cached)")
    print("  3. Unstaged changes only")
    print("  4. Compare against specific branch or commit ref (e.g. main, HEAD~1)")
    
    choice = input("\nEnter choice [1-4] (default: 1): ").strip()
    diff_type = "auto"
    target_ref = None

    if choice == "2":
        diff_type = "staged"
    elif choice == "3":
        diff_type = "unstaged"
    elif choice == "4":
        target_ref = input("Enter target ref/branch name (e.g. main, origin/main, HEAD~2): ").strip()
        if not target_ref:
            target_ref = "main"

    print("\nSelect LLM Provider (press Enter to keep default from .env):")
    providers_list = list(PROVIDERS.keys())
    for idx, p in enumerate(providers_list, start=1):
        print(f"  {idx}. {p}")
    provider_choice = input(f"Enter provider [1-{len(providers_list)}] or name: ").strip()

    provider_name = None
    if provider_choice.isdigit() and 1 <= int(provider_choice) <= len(providers_list):
        provider_name = providers_list[int(provider_choice) - 1]
    elif provider_choice.lower() in PROVIDERS:
        provider_name = provider_choice.lower()

    custom_instructions = input("\nAny custom review instructions? (Optional, press Enter to skip): ").strip()

    return {
        "diff_type": diff_type,
        "target_ref": target_ref,
        "provider": provider_name,
        "instructions": custom_instructions if custom_instructions else None,
    }


def main():
    parser = argparse.ArgumentParser(
        description="git-diff-reviewer: Terminal-based AI code reviewer for git diffs."
    )
    
    # Diff target options
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "-s", "--staged",
        action="store_true",
        help="Review staged changes only (git diff --cached)"
    )
    target_group.add_argument(
        "-u", "--unstaged",
        action="store_true",
        help="Review unstaged working tree changes only (git diff)"
    )
    target_group.add_argument(
        "-b", "--branch", "--ref",
        dest="ref",
        metavar="REF",
        help="Compare working tree against a branch or commit (e.g. main, origin/main, HEAD~1)"
    )

    # Provider & Model overrides
    parser.add_argument(
        "-p", "--provider",
        choices=list(PROVIDERS.keys()),
        help=f"Override LLM provider ({', '.join(PROVIDERS.keys())})"
    )
    parser.add_argument(
        "-m", "--model",
        help="Override model name for the selected provider"
    )

    # Extra prompt instructions
    parser.add_argument(
        "-n", "--instructions",
        help="Additional custom instructions to append to the review prompt"
    )

    # Output options
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Save generated review output to a markdown file"
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw markdown text without rich terminal formatting"
    )

    # Utility flags
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run in interactive selection mode"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display repository status and provider configuration, then exit"
    )

    args = parser.parse_args()

    # Handle status flag
    if args.status:
        show_status(provider_override=args.provider, model_override=args.model)
        sys.exit(0)

    # Check Git repository
    if not is_git_repository():
        print_error("Fatal: Not a git repository (or any of the parent directories).")
        print_info("Please navigate to a git repository and run this command again.")
        sys.exit(1)

    # Interactive mode check
    diff_type = "auto"
    target_ref = args.ref
    provider_name = args.provider
    custom_instructions = args.instructions

    if args.interactive:
        opts = interactive_mode()
        diff_type = opts["diff_type"]
        target_ref = opts["target_ref"]
        if opts["provider"]:
            provider_name = opts["provider"]
        if opts["instructions"]:
            custom_instructions = opts["instructions"]
    elif args.staged:
        diff_type = "staged"
    elif args.unstaged:
        diff_type = "unstaged"

    # Step 1: Initialize Provider
    try:
        provider = get_llm_provider(
            provider_name=provider_name,
            model_name=args.model
        )
    except LLMConfigurationError as e:
        print_error(f"Configuration Error: {str(e)}")
        print_info("Check your .env file or copy .env.example to .env to set up API keys.")
        sys.exit(1)

    # Step 2: Extract Git Diff
    try:
        diff_content, diff_stat, detected_type = get_git_diff(
            diff_type=diff_type,
            target_ref=target_ref
        )
    except GitError as e:
        print_error(f"Git Error: {str(e)}")
        sys.exit(1)

    if not diff_content or not diff_content.strip():
        print_warning(f"No changes found for review ({detected_type}).")
        print_info("Make some edits or stage changes (`git add .`), then run git-diff-reviewer again.")
        sys.exit(0)

    # Print summary header
    if RICH_AVAILABLE and not args.raw:
        console.print(Panel(
            f"[bold cyan]Review Target:[/bold cyan] {detected_type}\n"
            f"[bold cyan]Provider:[/bold cyan] {provider.provider_name} | [bold cyan]Model:[/bold cyan] {provider.model}\n"
            f"[bold cyan]Diff Stats:[/bold cyan]\n{diff_stat if diff_stat else 'No stat summary'}",
            title="[bold blue]Git Diff Reviewer[/bold blue]",
            border_style="blue"
        ))
    else:
        print(f"\n--- Reviewing: {detected_type} ---")
        print(f"Provider: {provider.provider_name} | Model: {provider.model}")
        if diff_stat:
            print(f"Diff Stats:\n{diff_stat}")
        print("--------------------------------\n")

    # Step 3: Truncate and Build Prompt
    safe_diff = truncate_diff(diff_content)
    system_prompt, user_prompt = build_review_prompt(
        diff_text=safe_diff,
        diff_stat=diff_stat,
        extra_instructions=custom_instructions
    )

    # Step 4: Query LLM Provider
    print_info(f"Sending diff to {provider.provider_name} ({provider.model})...")

    try:
        if RICH_AVAILABLE and not args.raw:
            with console.status(f"[bold green]Analyzing diff with {provider.provider_name}...[/bold green]", spinner="dots"):
                review_markdown = provider.generate_review(
                    prompt=user_prompt,
                    system_prompt=system_prompt
                )
        else:
            print(f"Analyzing diff with {provider.provider_name}...")
            review_markdown = provider.generate_review(
                prompt=user_prompt,
                system_prompt=system_prompt
            )
    except LLMProviderError as e:
        print_error(f"LLM Provider Failed: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print_warning("\nOperation cancelled by user.")
        sys.exit(130)

    # Step 5: Render and optionally save output
    render_markdown(review_markdown, raw=args.raw)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(f"# Code Review - {detected_type}\n\n")
                f.write(f"**Provider**: {provider.provider_name} | **Model**: {provider.model}\n\n")
                if diff_stat:
                    f.write(f"### Diff Stats\n```text\n{diff_stat}\n```\n\n")
                f.write(review_markdown)
            print_success(f"Review saved successfully to: {args.output}")
        except IOError as e:
            print_error(f"Failed to write review output to file '{args.output}': {str(e)}")


if __name__ == "__main__":
    main()
