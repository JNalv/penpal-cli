# penpal

Async Claude via the Batch API. Half the cost, none of the rush.

Penpal is a CLI for sending prompts to Claude through Anthropic's [Batch API](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing), which processes requests asynchronously at **50% off**. Submit a prompt, go do something else, come back and read the response.

## Install

```bash
pipx install penpal-cli
```

Or with pip:

```bash
pip install penpal-cli
```

Requires Python 3.11+.

## Quick start

```bash
# 1. Store your API key (one-time setup)
penpal auth

# 2. Submit a prompt
penpal ask "Explain the CAP theorem in plain English"

# 3. Check if it's done
penpal status

# 4. Read the response
penpal read --latest
```

Batch requests typically complete in minutes. Use `penpal status --watch` to auto-refresh.

## Features

### Model aliases

Use short names instead of full model identifiers:

| Alias    | Model                          |
|----------|--------------------------------|
| `haiku`  | `claude-haiku-4-5-20251001`    |
| `sonnet` | `claude-sonnet-4-20250514`     |
| `opus`   | `claude-opus-4-20250514`       |

```bash
penpal ask -m haiku "Quick question"
```

### File attachments

Attach images, PDFs, and text files directly:

```bash
penpal ask -f screenshot.png "What's in this image?"
penpal ask -f paper.pdf "Summarize this paper"
penpal ask -f main.py -f utils.py "Review these files"
```

### Batch mode

Process an entire directory of files in a single batch:

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

### Code extraction

Extract fenced code blocks from responses directly to files:

```bash
penpal read --latest --extract
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

### Raw output for piping

`--raw` strips all formatting, ideal for piping into other tools or feeding back to an AI coding agent:

```bash
penpal read --latest --raw | pbcopy
penpal read --latest --raw > response.md
```

## Claude Code integration

Teach [Claude Code](https://docs.anthropic.com/en/docs/claude-code) about penpal so it can use cheaper batch requests:

```bash
penpal setup-claude-code
```

This appends a small instruction block to `~/.claude/CLAUDE.md`. Remove it with `penpal uninstall-claude-code`.

### AGENTS.md (cross-agent standard)

For projects using multiple AI coding agents (Copilot, Cursor, OpenCode, Codex, etc.), add penpal instructions to the [AGENTS.md](https://github.com/anthropics/agents-md) standard:

```bash
penpal setup-agents-md
```

This writes to `./AGENTS.md` in the current directory. Remove it with `penpal uninstall-agents-md`.

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
max_tokens = 4096
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
