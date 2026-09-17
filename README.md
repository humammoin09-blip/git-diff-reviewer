# Git Diff Reviewer 

A modular, terminal-based CLI tool that inspects local git diffs and sends them to your choice of LLM provider for an automated, high-rigor security and code quality review.

---

## 🌟 Key Features

- **Multi-Provider Support**: Seamlessly switch between **OpenRouter**, **Google Gemini**, **Groq**, and local **Ollama** models.
- **Flexible Diff Targets**: Review staged changes (`--staged`), unstaged changes (`--unstaged`), or diff against specific branches/commits (`--branch main`).
- **Interactive Mode**: Guided terminal prompts for picking diff targets and providers on the fly.
- **Strict Review Taxonomy**: Highlights Critical Bugs, Security Vulnerabilities (OWASP/CWE/Secret leaks), Anti-patterns, and Performance Bottlenecks with actionable Before/After code snippets.
- **Rich Terminal Rendering**: Formatted markdown and colorized panels right in your terminal.
- **Safe Truncation**: Automatically manages large diffs to avoid LLM token context overflow.
- **Export to Markdown**: Save reviews directly to `.md` files for pull request comments or audit logs.

---

##  Quick Start

### 1. Clone & Setup

```bash
cd git-diff-reviewer
python -m venv .venv

# Activate on Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Activate on Linux/macOS
# source .venv/bin/activate

# Option A: Install dependencies directly
pip install -r requirements.txt

# Option B: Install as a global/editable CLI tool ('git-review' / 'git-diff-reviewer')
pip install -e .
```

### 2. Configure `.env`

Copy the template:

```bash
cp .env.example .env
# Or on Windows PowerShell:
Copy-Item .env.example .env
```

Open `.env` and configure your chosen provider and API key.

---

## ⚙️ Provider Configuration

You can configure the active provider in `.env` using `LLM_PROVIDER`:

### 1. OpenRouter (`LLM_PROVIDER=openrouter`)
Access Claude 3.5 Sonnet, GPT-4o, Gemini 2.0, Llama 3.3, and hundreds of other models through one unified API.

```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx
LLM_MODEL=anthropic/claude-3.5-sonnet  # (Optional, default is anthropic/claude-3.5-sonnet)
```

### 2. Google Gemini (`LLM_PROVIDER=gemini`)
Fast and deeply capable code reviews via Google's Gemini models.

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzasyxxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gemini-3.6-flash  
```

### 3. Groq (`LLM_PROVIDER=groq`)
Ultra-low-latency inference using Llama 3.3 models.

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
LLM_MODEL=llama-3.3-70b-versatile  # (Optional)
```

### 4. Ollama Local (`LLM_PROVIDER=ollama`)
100% private and offline code reviews running on your own machine.

1. Ensure Ollama is running:
   ```bash
   ollama run llama3
   # or
   ollama run codellama
   ```
2. Configure `.env`:
   ```env
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434  # (Default)
   LLM_MODEL=llama3                      # (or codellama, deepseek-r1:8b, qwen2.5-coder)
   ```

---

## 💻 CLI Usage & Examples

### Basic Commands

```bash
# Auto-detect changes (reviews staged changes if present, otherwise unstaged)
python main.py

# Review staged changes only
python main.py --staged
# or
python main.py -s

# Review unstaged changes only
python main.py --unstaged
# or
python main.py -u

# Compare working branch against main branch or specific commit
python main.py --branch main
python main.py -b HEAD~2
```

### Override Provider & Model on the Fly

You don't need to edit `.env` for one-off reviews:

```bash
# Use Groq for a quick review
python main.py -s --provider groq

# Use Ollama locally with a specific coding model
python main.py -s --provider ollama --model qwen2.5-coder

# Use Gemini with custom model
python main.py -s --provider gemini --model gemini-1.5-pro
```

### Interactive Mode

Run with `-i` to enter an interactive selection wizard:

```bash
python main.py -i
```

### Export Review Output

Save the review output directly to a file:

```bash
python main.py -s --output code_review.md
```

### Add Custom Focus Instructions

Instruct the LLM to focus on specific requirements (e.g. concurrency, memory safety):

```bash
python main.py -s --instructions "Focus heavily on thread safety and resource locking."
```

### Check Status

Check current git status, active ignore rules, pre-commit hook status, and configured provider:

```bash
python main.py --status
```

---

## 🪝 Pre-commit Git Hook Automation

Automatically trigger AI code reviews whenever a developer runs `git commit`.

### 1. Install the Pre-commit Hook

Run either of the following commands from your repository root:

```bash
# Via main CLI
python main.py --install-hook

# Or via dedicated installer script
python hooks/install_hook.py
```

This installs the hook script into your local `.git/hooks/pre-commit` file and sets appropriate execution permissions. If an existing foreign hook is present, a backup (`pre-commit.backup`) is created automatically.

### 2. How it Works on `git commit`

When you stage changes and run `git commit`:
1. The hook executes `python main.py --staged`.
2. Staged changes are retrieved and filtered against `.reviewerignore` patterns.
3. The clean diff is sent to your configured LLM provider.
4. The structured code review is printed directly in your terminal.

```bash
git add src/app.py
git commit -m "feat: update authentication logic"
# => [git-diff-reviewer] Running pre-commit AI code review...
# => AI Code Review Output is displayed in your terminal before commit finishes!
```

### 3. Uninstall the Hook

To remove the hook (and restore any previous backup):

```bash
python main.py --uninstall-hook
# or
python hooks/install_hook.py --uninstall
```

---

## Custom Ignore Configuration (`.reviewerignore`)

You can exclude noisy or generated files (such as lockfiles, build outputs, and minified bundles) from being sent to the LLM.

- **Automatic Root Detection**: Place a `.reviewerignore` file at the root of your repository.
- **Smart Fallback**: If `.reviewerignore` is not present, `git-diff-reviewer` automatically applies smart defaults (e.g. `package-lock.json`, `*.lock`, `dist/`, `build/`, `.env`, `node_modules/`, minified assets).

### Example `.reviewerignore`:
```text
# Package manager lockfiles
package-lock.json
*.lock

# Build outputs & dependencies
node_modules/
dist/
build/
.venv/

# Environment files
.env
.env.*

# Minified assets & maps
*.min.js
*.min.css
*.map
```

---

## 📁 File Structure

```text
git-diff-reviewer/
├── pyproject.toml      # Modern PEP 518/621 build configuration
├── setup.py            # Legacy/compatibility setuptools script
├── .env.example        # Template for environment configuration
├── .reviewerignore     # Custom file/folder ignore pattern configuration
├── .gitignore          # Git ignore rules
├── requirements.txt    # Python package dependencies
├── llm.py              # Modular LLM client & provider implementations
├── reviewer.py         # Git diff extraction & prompt construction
├── ignore.py           # Pattern matching & diff filtering engine
├── hooks/              # Pre-commit hook automation package & installer
│   ├── __init__.py
│   ├── manager.py
│   └── install_hook.py
├── main.py             # CLI application entrypoint
├── tests/              # Comprehensive unit test suite (22 tests)
│   ├── test_llm.py
│   ├── test_reviewer.py
│   ├── test_ignore.py
│   └── test_hooks.py
└── README.md           # Documentation & user guide
```
---
## 🧪 Testing

Run the included test suite to verify git diff parsing and LLM provider implementations:

```bash
python -m unittest discover tests
```
---
## 📄 License

MIT License. Feel free to modify and adapt for your team's workflow!
