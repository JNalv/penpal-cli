"""Click-based CLI entry point for Penpal."""
from __future__ import annotations

import getpass
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich import box

from penpal import __version__
from penpal.auth import AuthError, delete_api_key, get_api_key, get_key_status, store_api_key
from penpal.builder import build_single_request, resolve_model
from penpal.client import APIError, AuthAPIError, BillingError, check_batch, get_results, submit_batch, validate_api_key
from penpal.config import MODEL_ALIASES, load_config
from penpal.cost import estimate_cost, format_cost
from penpal import db
from penpal.db import init_db

console = Console()
err_console = Console(stderr=True)


def _get_db_path():
    cfg = load_config()
    init_db(cfg.db_path)
    return cfg.db_path


def _ago(dt_str: str) -> str:
    """Format a datetime string as a human-readable 'X ago' string."""
    try:
        dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        if seconds < 3600:
            return f"{seconds // 60}m ago"
        if seconds < 86400:
            return f"{seconds // 3600}h ago"
        return f"{seconds // 86400}d ago"
    except Exception:
        return dt_str


def _status_icon(status: str) -> str:
    icons = {
        "processing": "⏳",
        "completed": "✓",
        "failed": "✗",
        "expired": "⌛",
        "cancelled": "⊘",
    }
    return icons.get(status, status)


def _since_to_datetime(since: str) -> Optional[str]:
    now = datetime.now(tz=timezone.utc)
    mapping = {
        "today": now.replace(hour=0, minute=0, second=0, microsecond=0),
        "yesterday": (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
    }
    dt = mapping.get(since)
    return dt.isoformat() if dt else None


@click.group()
@click.version_option(__version__, prog_name="penpal")
def main():
    """Penpal — async Claude via Batch API. Half the cost, none of the rush."""
    pass


# ---------------------------------------------------------------------------
# penpal auth
# ---------------------------------------------------------------------------

@main.command("auth")
@click.option("--status", is_flag=True, help="Show key status without changing it.")
def auth_cmd(status: bool):
    """Store your Anthropic API key securely."""
    if status:
        info = get_key_status()
        console.print(f"[bold]API Key Status[/bold]")
        console.print(f"  Active source : {info['source']}")
        console.print(f"  Active key    : {info['active']}")
        console.print(f"  Env var       : {info['env_var']}")
        console.print(f"  Keyring       : {info['keyring']}")
        console.print(f"  File fallback : {info['file']}")
        return

    key = getpass.getpass("Anthropic API key (sk-ant-api...): ")
    if not key.startswith("sk-ant-api"):
        err_console.print("[red]✗[/red] Key must start with 'sk-ant-api'. Please check and try again.")
        sys.exit(1)

    console.print("Validating key...", end=" ")
    try:
        validate_api_key(key)
    except AuthAPIError as e:
        err_console.print(f"\n[red]✗[/red] {e}")
        sys.exit(1)

    method = store_api_key(key)
    if method == "keyring":
        console.print("[green]✓[/green] API key validated and saved to system keychain.")
    else:
        console.print(f"[yellow]⚠[/yellow] No system keychain detected. Key stored in file (permissions restricted).")


@main.command("logout")
def logout_cmd():
    """Remove your stored API key."""
    deleted = delete_api_key()
    if deleted:
        console.print("[green]✓[/green] API key removed.")
    else:
        console.print("No stored API key found.")


# ---------------------------------------------------------------------------
# penpal ask
# ---------------------------------------------------------------------------

@main.command("ask")
@click.argument("prompt", required=False)
@click.option("--model", "-m", default=None, help="Model name or alias (haiku, sonnet, opus).")
@click.option("--system", "-s", type=click.Path(exists=True), default=None, help="Path to system prompt file.")
@click.option("--max-tokens", default=None, type=int, help="Max output tokens.")
@click.option("--tag", "-t", default=None, help="Human-readable tag for this request.")
@click.option("--stdin", "read_stdin", is_flag=True, help="Read prompt from stdin.")
def ask_cmd(
    prompt: Optional[str],
    model: Optional[str],
    system: Optional[str],
    max_tokens: Optional[int],
    tag: Optional[str],
    read_stdin: bool,
):
    """Submit a prompt to the Batch API."""
    cfg = load_config()
    db_path = cfg.db_path
    init_db(db_path)

    # Resolve prompt
    if read_stdin:
        prompt = sys.stdin.read().strip()
    if not prompt:
        raise click.UsageError("Provide a prompt as an argument or use --stdin.")

    # Resolve model
    resolved_model = resolve_model(model or cfg.model)

    # Resolve system prompt
    system_text: Optional[str] = None
    if system:
        system_text = open(system).read()

    # Resolve max_tokens
    mt = max_tokens or cfg.max_tokens

    # Get API key
    try:
        api_key = get_api_key()
    except AuthError as e:
        err_console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    # Build and submit
    request_obj = build_single_request(
        prompt=prompt,
        model=resolved_model,
        max_tokens=mt,
        system_prompt=system_text,
    )

    try:
        batch_id = submit_batch(api_key, [request_obj])
    except AuthAPIError as e:
        err_console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except BillingError as e:
        err_console.print(f"[red]✗[/red] {e}")
        sys.exit(1)
    except APIError as e:
        err_console.print(f"[red]✗[/red] {e}")
        sys.exit(1)

    # Store in DB
    db.save_request(
        db_path=db_path,
        batch_id=batch_id,
        model=resolved_model,
        user_prompt=prompt,
        max_tokens=mt,
        custom_id=request_obj["custom_id"],
        system_prompt=system_text,
        tag=tag,
    )

    console.print(f"[green]✓[/green] Submitted 1 request (batch: {batch_id})")
    if tag:
        console.print(f"  Tag: {tag}")


# ---------------------------------------------------------------------------
# penpal status
# ---------------------------------------------------------------------------

@main.command("status")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all requests.")
@click.option("--limit", "-n", default=10, help="Number of requests to show.")
@click.option("--watch", "-w", is_flag=True, help="Continuously refresh.")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON.")
def status_cmd(show_all: bool, limit: int, watch: bool, output_json: bool):
    """Show status of pending and recent requests."""
    import time as _time

    cfg = load_config()
    db_path = cfg.db_path
    init_db(db_path)

    def _run():
        try:
            api_key = get_api_key()
        except AuthError:
            api_key = None

        # Poll pending requests first
        if api_key:
            pending = db.get_pending_requests(db_path)
            for req in pending:
                try:
                    result = check_batch(api_key, req.batch_id)
                    if result["status"] == "ended":
                        # Determine final status
                        counts = result["counts"]
                        if counts["errored"] > 0 and counts["succeeded"] == 0:
                            final_status = "failed"
                        elif counts["expired"] > 0 and counts["succeeded"] == 0:
                            final_status = "expired"
                        else:
                            final_status = "completed"
                        db.update_request_status(
                            db_path, req.batch_id, final_status,
                            completed_at=datetime.now(tz=timezone.utc).isoformat()
                        )
                except AuthAPIError as e:
                    err_console.print(f"[red]✗[/red] Auth error: {e}")
                    break
                except APIError:
                    pass  # Transient error — show stale status, don't abort

        requests = db.get_recent_requests(db_path, limit=limit, include_all=show_all)

        if output_json:
            data = []
            for r in requests:
                data.append({
                    "batch_id": r.batch_id,
                    "model": r.model,
                    "status": r.status,
                    "tag": r.tag,
                    "created_at": r.created_at,
                    "estimated_cost": r.estimated_cost,
                })
            click.echo(json.dumps(data, indent=2))
            return

        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Model")
        table.add_column("Status")
        table.add_column("Age")
        table.add_column("Tag")
        table.add_column("Cost", justify="right")

        for r in requests:
            short_id = r.batch_id[:12] if len(r.batch_id) > 12 else r.batch_id
            model_short = r.model.split("-")[1] if "-" in r.model else r.model
            status_display = f"{_status_icon(r.status)} {r.status}"
            age = _ago(r.created_at)
            tag = r.tag or "—"
            cost = format_cost(r.estimated_cost or 0.0)
            table.add_row(short_id, model_short, status_display, age, tag, cost)

        console.print(table)

    if watch:
        try:
            while True:
                console.clear()
                _run()
                console.print(f"\n[dim]Refreshing every {cfg.poll_interval}s. Ctrl+C to stop.[/dim]")
                _time.sleep(cfg.poll_interval)
        except KeyboardInterrupt:
            pass
    else:
        _run()


# ---------------------------------------------------------------------------
# penpal read
# ---------------------------------------------------------------------------

@main.command("read")
@click.argument("batch_id_or_tag", required=False)
@click.option("--latest", is_flag=True, help="Read the most recently completed response.")
@click.option("--full", is_flag=True, help="Print complete response without truncation.")
@click.option("--raw", is_flag=True, help="Print raw text with no Rich formatting.")
@click.option("--index", "-i", default=None, type=int, help="For multi-request batches: read the Nth result.")
def read_cmd(
    batch_id_or_tag: Optional[str],
    latest: bool,
    full: bool,
    raw: bool,
    index: Optional[int],
):
    """Retrieve and display a completed response."""
    cfg = load_config()
    db_path = cfg.db_path
    init_db(db_path)

    # Resolve which request to read
    req = None
    if latest:
        req = db.get_latest_completed(db_path)
        if not req:
            err_console.print("[red]✗[/red] No completed requests found.")
            sys.exit(1)
    elif batch_id_or_tag:
        req = db.get_request_by_batch_id(db_path, batch_id_or_tag)
        if not req:
            req = db.get_request_by_tag(db_path, batch_id_or_tag)
        if not req:
            err_console.print(f"[red]✗[/red] No request found for '{batch_id_or_tag}'.")
            sys.exit(1)
    else:
        raise click.UsageError("Provide a batch ID / tag, or use --latest.")

    # If still processing, check status
    if req.status == "processing":
        try:
            api_key = get_api_key()
            result = check_batch(api_key, req.batch_id)
            if result["status"] == "ended":
                counts = result["counts"]
                final_status = "failed" if (counts["errored"] > 0 and counts["succeeded"] == 0) else "completed"
                db.update_request_status(
                    db_path, req.batch_id, final_status,
                    completed_at=datetime.now(tz=timezone.utc).isoformat()
                )
                # Reload
                req = db.get_request_by_batch_id(db_path, req.batch_id)
        except AuthError:
            pass

    if req.status == "processing":
        console.print(f"[yellow]⏳[/yellow] Batch {req.batch_id} is still processing.")
        console.print(f"  Submitted {_ago(req.created_at)}. Check back soon.")
        return

    if req.status in ("failed", "expired"):
        err_console.print(f"[red]✗[/red] Batch {req.batch_id} {req.status}.")
        sys.exit(1)

    # Check if we have responses cached
    responses = db.get_responses(db_path, req.id)

    if not responses:
        # Fetch from API
        try:
            api_key = get_api_key()
        except AuthError as e:
            err_console.print(f"[red]✗[/red] {e}")
            sys.exit(1)

        try:
            results = get_results(api_key, req.batch_id)
        except APIError as e:
            err_console.print(f"[red]✗[/red] {e}")
            sys.exit(1)

        total_input = 0
        total_output = 0
        for br in results:
            if br.status == "succeeded" and br.content is not None:
                cost = estimate_cost(req.model, br.input_tokens or 0, br.output_tokens or 0)
                db.save_response(
                    db_path=db_path,
                    request_id=req.id,
                    content=br.content,
                    custom_id=br.custom_id,
                    input_tokens=br.input_tokens,
                    output_tokens=br.output_tokens,
                    estimated_cost=cost,
                )
                total_input += br.input_tokens or 0
                total_output += br.output_tokens or 0

        total_cost = estimate_cost(req.model, total_input, total_output)
        db.update_request_status(
            db_path, req.batch_id, "completed",
            completed_at=req.completed_at or datetime.now(tz=timezone.utc).isoformat(),
            input_tokens=total_input,
            output_tokens=total_output,
            estimated_cost=total_cost,
        )

        responses = db.get_responses(db_path, req.id)

    if not responses:
        err_console.print("[red]✗[/red] No response content found.")
        sys.exit(1)

    # Multi-request batch listing
    if req.is_multi and index is None:
        console.print(f"Batch [cyan]{req.batch_id}[/cyan] contains {len(responses)} results:")
        for i, resp in enumerate(responses):
            fname = resp.file_name or resp.custom_id or f"result-{i}"
            tokens = (resp.input_tokens or 0) + (resp.output_tokens or 0)
            console.print(f"  [{i}] {fname}  ✓ done  ({tokens:,} tokens)")
        console.print(f"\nUse `penpal read {req.batch_id} -i <N>` to read a specific result.")
        return

    # Select which response to show
    if index is not None:
        if index >= len(responses):
            err_console.print(f"[red]✗[/red] Index {index} out of range (0–{len(responses)-1}).")
            sys.exit(1)
        resp = responses[index]
    else:
        resp = responses[0]

    db.mark_as_read(db_path, req.batch_id)

    content = resp.content
    if raw:
        click.echo(content)
        return

    # Rich formatted output
    if not full and cfg.preview_lines < len(content.splitlines()):
        lines = content.splitlines()[:cfg.preview_lines]
        content = "\n".join(lines)
        truncated = True
    else:
        truncated = False

    console.print(content)
    if truncated:
        console.print(f"\n[dim][truncated — use --full for complete response][/dim]")


# ---------------------------------------------------------------------------
# penpal config
# ---------------------------------------------------------------------------

@main.command("config")
@click.option("--path", is_flag=True, help="Print config file path.")
@click.option("--edit", is_flag=True, help="Open config.toml in $EDITOR.")
def config_cmd(path: bool, edit: bool):
    """Show resolved configuration."""
    import os, subprocess
    cfg = load_config()
    if path:
        click.echo(str(cfg.config_file))
        return
    if edit:
        editor = os.environ.get("EDITOR", "nano")
        cfg.config_file.parent.mkdir(parents=True, exist_ok=True)
        subprocess.call([editor, str(cfg.config_file)])
        return
    console.print(f"[bold]Penpal Configuration[/bold]")
    console.print(f"  model          = {cfg.model}")
    console.print(f"  max_tokens     = {cfg.max_tokens}")
    console.print(f"  poll_interval  = {cfg.poll_interval}s")
    console.print(f"  preview_lines  = {cfg.preview_lines}")
    console.print(f"  db_path        = {cfg.db_path}")
    console.print(f"  config_file    = {cfg.config_file}")
    console.print(f"  skills_dir     = {cfg.skills_dir}")
    console.print(f"\n[bold]Model Aliases[/bold]")
    for alias, full in MODEL_ALIASES.items():
        console.print(f"  {alias:8} → {full}")
