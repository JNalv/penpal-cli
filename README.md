# penpal

Async Claude via the Batch API. Half the cost, easier bulk/repeat processing, and no rush 😎

Penpal is a CLI for sending prompts to Claude through Anthropic's [Batch API](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing), which processes requests asynchronously at **50% off**. Submit a prompt (or a thousand!), go do something else, then come back and call the output exactly when you need it.

## Install

```bash
pipx install penpal-cli
```

Or with pip:

```bash
pip install penpal-cli
```

Requires Python 3.11+.

## Why Penpal?

| Use Case | Why Penpal | Example |
|----------|-----------|---------|
| **Bulk analysis** | 50% cheaper, ideal for processing 100s of files | Summarize 500 research papers, review 50 PRs |
| **AI coding agents** | CLI integrates with Claude Code, Cursor, VS Code, et al. | Let your IDE run expensive queries in the background |
| **Evaluations** | Process thousands of test cases at batch pricing | Run LLM evaluation suites on a budget |
| **Scheduled workflows** | Fire off a prompt and check results tomorrow | Generate daily reports, batch content creation, batch moderation |
| **Spend smarter!** | Deploy your money & tokens more strategically | Get big docs and big answers a little later, for half the price |

## Quick start

```bash
# 1. Store your API key (one-time setup)
penpal auth

# 2. Submit a prompt
penpal ask "Explain the CAP theorem in plain English"

# 3a. Check if it's done once...
penpal status

# 3b. Or, keep tabs with the Terminal program
penpal session

# 4. Read the response
penpal read --latest
```

Batch requests typically complete in minutes—sometimes under 10 seconds for small requests. Use `penpal status --watch` to auto-refresh.

## What works (and what doesn't)

The Batch API supports **all Messages API features** except streaming. Here's what that means:

| Feature | Status | Notes |
|---------|--------|-------|
| **Vision (images, screenshots)** | ✅ Works | Analyze images at batch pricing |
| **File attachments (PDFs, code)** | ✅ Works | Pass files directly to Claude |
| **Tool use & function calling** | ✅ Works | Build agentic workflows on a budget |
| **System prompts & skills** | ✅ Works | Full control with reusable system prompts |
| **Max tokens / temperature** | ✅ Works | All inference parameters supported |
| **Streaming responses** | ❌ No | Responses are complete when retrieved |
| **MCP (Model Context Protocol)** | ❌ No | Requires real-time bidirectional interaction |
| **Real-time chat** | ❌ No | Async-only — no live conversations |

In short: Use Penpal for **any task that doesn't need immediate answers**. Perfect for bulk analysis, evaluations, content generation, and code review.

## Works with AI coding assistants

Since Penpal is CLI-powered, your favorite coding assistant can cheaply send expensive queries into the background. Imagine:

- 📝 **Async Claude in your IDE**: Let a cheaper model ask Opus a tough question for half the price, then pull the answer back into context when ready.
- 🎯 **Batch processing in automation**: Submit 500 summaries at once, retrieve them as needed without bloating your context window.
- ⚡ **Scheduled workflows**: Run expensive evaluations or code reviews overnight at batch pricing.

No streaming delays, no token-counting anxiety — just submit and move on.

### Claude Code

Teach [Claude Code](https://docs.anthropic.com/en/docs/claude-code) about Penpal so it can use cheaper batch requests:

```bash
penpal setup-claude-code
```

This appends a small instruction block to `~/.claude/CLAUDE.md`, which works globally. Remove it with `penpal uninstall-claude-code`.

### AGENTS.md (cross-agent standard)

For projects using other AI coding agents (Copilot, Cursor, OpenCode, Codex, etc.), add Penpal instructions to the [AGENTS.md](https://github.com/anthropics/agents-md) standard:

```bash
penpal setup-agents-md
```

This writes to `./AGENTS.md` in the current directory. Remove it with `penpal uninstall-agents-md`.

### Batch mode

A batch can contain multiple requests. Process an entire directory of files in a single batch:

```bash
penpal ask -b ./documents/ "Summarize this document"
```

Each file becomes a separate request. Use `penpal read <id> -i <N>` to read individual results.

### Skills (reusable system prompts)

Create and reuse system prompts as named skills:

```bash
penpal skills add code-review    # Opens $EDITOR
penpal ask --skill code-review -f app.py "Review this"
penpal skills                    # List all skills
```
You can also add skills manually to `~/.config/penpal/skills`.

### File attachments

Attach images, PDFs, and text files directly:

```bash
penpal ask -f screenshot.png "What's in this image?"
penpal ask -f paper.pdf "Summarize this paper"
penpal ask -f main.py -f utils.py "Review these files"
```

### Code extraction

Extract fenced code blocks from responses directly to files:

```bash
penpal read --latest --extract
```

### Raw output for piping

`--raw` strips all formatting, ideal for piping into other tools or feeding back to an AI coding agent:

```bash
penpal read --latest --raw | pbcopy
penpal read --latest --raw > response.md
```

### TUI dashboard

Launch an interactive terminal dashboard with live status updates, cost tracking, manual request creation, and more:

```bash
penpal session
```

### History and cost tracking

```bash
penpal history                   # Browse past requests
penpal history --cost            # See spending summary
penpal history --since 7d        # Filter by time
penpal history --search "CAP"    # Search prompts
```

### Model aliases

Use short names instead of full model identifiers:

| Alias    | Model                          |
|----------|--------------------------------|
| `haiku`  | `claude-haiku-4-5-20251001`    |
| `sonnet` | `claude-sonnet-4-20250514`     |
| `opus`   | `claude-opus-4-20250514`       |

```bash
penpal ask -m haiku "What was Pangaea?"
```

## Configuration

Penpal uses XDG directories. Config file location:

```bash
penpal config --path   # ~/.config/penpal/config.toml
penpal config --edit   # Open in $EDITOR
penpal config          # Show resolved settings
```

Example `config.toml`:

```toml
model = "sonnet"
max_tokens = 8192
poll_interval = 180
preview_lines = 40
```

### Environment variables

| Variable             | Description                      |
|----------------------|----------------------------------|
| `ANTHROPIC_API_KEY`  | API key (overrides stored key)   |
| `PENPAL_MODEL`       | Default model                    |
| `PENPAL_MAX_TOKENS`  | Default max output tokens        |
| `PENPAL_POLL_INTERVAL` | Status polling interval (seconds) |

## License

MIT
