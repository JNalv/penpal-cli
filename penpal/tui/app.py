"""Main Textual application for Penpal TUI dashboard."""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.containers import VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    Static,
    TextArea,
)

from penpal import db
import penpal.skills as skills_mod
from penpal.auth import AuthError, get_api_key
from penpal.client import APIError, AuthAPIError, check_batch, get_results, submit_batch
from penpal.builder import build_single_request, resolve_model
from penpal.config import MODEL_ALIASES, load_config
from penpal.cost import estimate_cost
from penpal.db import init_db
from penpal.models import Request, Response
from penpal.tui.dashboard import RequestTable
from penpal.tui.detail import DetailPane


# ---------------------------------------------------------------------------
# Data transfer object for the new-batch form
# ---------------------------------------------------------------------------

@dataclass
class NewBatchParams:
    prompt: str
    model: str                  # full model string (already resolved)
    skill_name: Optional[str]
    tag: Optional[str]
    file_paths: list[Path] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Modal screens
# ---------------------------------------------------------------------------

class ConfirmScreen(ModalScreen[bool]):
    """Simple yes/no confirmation dialog."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Static(id="confirm-dialog"):
            yield Label(self._message)
            yield Button("Yes", id="yes", variant="warning")
            yield Button("No", id="no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class NewRequestScreen(ModalScreen[Optional[NewBatchParams]]):
    """Rich single-screen form for composing a new batch request."""

    DEFAULT_CSS = """
    NewRequestScreen {
        align: center middle;
    }
    #new-batch-dialog {
        width: 72;
        height: 80vh;
        border: solid $primary;
        background: $surface;
    }
    #form-scroll {
        padding: 1 2;
    }
    #form-scroll Label.section-label {
        color: $text-muted;
        margin-top: 1;
    }
    #form-scroll TextArea {
        height: 5;
        margin-bottom: 0;
    }
    #form-scroll RadioSet {
        height: auto;
        border: none;
        padding: 0;
    }
    #form-scroll Select {
        width: 100%;
    }
    #form-scroll Input {
        width: 100%;
    }
    #error-label {
        color: $error;
        height: auto;
        display: none;
    }
    #error-label.visible {
        display: block;
    }
    #btn-row {
        height: auto;
        margin-top: 1;
        align: right middle;
    }
    #btn-submit { margin-right: 1; }
    """

    def __init__(self, cfg, skills: list[tuple[str, str]]) -> None:
        super().__init__()
        self._cfg = cfg
        self._skills = skills  # [(name, description), ...]

    def compose(self) -> ComposeResult:
        # Determine default model radio from config
        default_alias = self._cfg.model  # e.g. "sonnet" or full string

        with VerticalScroll(id="new-batch-dialog"):
            with VerticalScroll(id="form-scroll"):
                yield Label("─── New Batch Request ───────────────────────────────")

                yield Label("Prompt", classes="section-label")
                yield TextArea(id="prompt-area", language=None)

                yield Label("Model", classes="section-label")
                with RadioSet(id="model-radio"):
                    yield RadioButton("haiku",  value=(default_alias in ("haiku",  MODEL_ALIASES["haiku"])),  id="rb-haiku")
                    yield RadioButton("sonnet", value=(default_alias in ("sonnet", MODEL_ALIASES["sonnet"])), id="rb-sonnet")
                    yield RadioButton("opus",   value=(default_alias in ("opus",   MODEL_ALIASES["opus"])),   id="rb-opus")

                yield Label("Skill  (optional)", classes="section-label")
                skill_options: list[tuple[str, str]] = [("— none —", "")]
                skill_options += [(f"{name}  —  {desc}", name) for name, desc in self._skills]
                yield Select(skill_options, value="", id="skill-select", allow_blank=False)

                yield Label("Tag  (optional)", classes="section-label")
                yield Input(placeholder="e.g. lit-review", id="tag-input")

                yield Label(
                    "Files  (optional — comma-separated paths; Tab-expand in your shell first)",
                    classes="section-label",
                )
                yield Input(placeholder="/path/to/file1.pdf, /path/to/image.png", id="files-input")

                yield Label("", id="error-label")

                with Static(id="btn-row"):
                    yield Button("Submit", id="btn-submit", variant="primary")
                    yield Button("Cancel", id="btn-cancel", variant="default")

    def on_mount(self) -> None:
        self.query_one("#prompt-area", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-submit":
            self._try_submit()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "ctrl+enter":
            self._try_submit()

    def _try_submit(self) -> None:
        error = self.query_one("#error-label", Label)

        # Prompt
        prompt = self.query_one("#prompt-area", TextArea).text.strip()
        if not prompt:
            error.update("Prompt cannot be empty.")
            error.add_class("visible")
            return

        # Model
        radio_set = self.query_one("#model-radio", RadioSet)
        alias_map = {0: "haiku", 1: "sonnet", 2: "opus"}
        # RadioSet.pressed_index gives the selected index (0-based)
        selected_alias = alias_map.get(radio_set.pressed_index, "sonnet")
        resolved_model = resolve_model(selected_alias)

        # Skill
        skill_value = self.query_one("#skill-select", Select).value
        skill_name = skill_value if skill_value else None

        # Tag
        tag_raw = self.query_one("#tag-input", Input).value.strip()
        tag = tag_raw or None

        # Files
        files_raw = self.query_one("#files-input", Input).value.strip()
        file_paths: list[Path] = []
        if files_raw:
            for part in files_raw.split(","):
                p = Path(part.strip())
                if not p.exists():
                    error.update(f"File not found: {p}")
                    error.add_class("visible")
                    return
                file_paths.append(p)

        error.remove_class("visible")
        self.dismiss(NewBatchParams(
            prompt=prompt,
            model=resolved_model,
            skill_name=skill_name,
            tag=tag,
            file_paths=file_paths,
        ))


class SearchScreen(ModalScreen[Optional[str]]):
    """Search/filter overlay."""

    def compose(self) -> ComposeResult:
        with Static(id="search-dialog"):
            yield Label("Search requests (Enter to filter, Escape to cancel):")
            yield Input(placeholder="Search by prompt or tag...", id="search-input")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class PenpalApp(App):
    """Penpal TUI — live batch request dashboard."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "copy_id", "Copy ID"),
        Binding("d", "delete_request", "Delete"),
        Binding("n", "new_request", "New"),
        Binding("/", "search", "Search"),
        Binding("p", "toggle_prompt", "Toggle prompt"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._cfg = load_config()
        init_db(self._cfg.db_path)
        self._requests: dict[str, Request] = {}
        self._responses_cache: dict[str, list[Response]] = {}

    def compose(self) -> ComposeResult:
        yield Static("Penpal  —  Batch API Monitor", id="header")
        yield RequestTable(id="request-table")
        yield DetailPane(id="detail-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._load_requests()
        self._update_header()
        self.set_interval(self._cfg.poll_interval, self._poll_batches_worker)

    def _load_requests(self, query: Optional[str] = None) -> None:
        if query:
            requests = db.search_requests(self._cfg.db_path, query, limit=200)
        else:
            requests = db.get_recent_requests(
                self._cfg.db_path, limit=200, include_all=True
            )
        self._requests = {r.batch_id: r for r in requests}
        self.query_one(RequestTable).populate(requests)

    def _update_header(self) -> None:
        pass  # header is static; nothing to update

    def _poll_batches_worker(self) -> None:
        self.run_worker(self._do_poll, exclusive=True, thread=True)

    def _do_poll(self) -> None:
        try:
            api_key = get_api_key()
        except AuthError:
            return

        pending = db.get_pending_requests(self._cfg.db_path)
        for req in pending:
            try:
                result = check_batch(api_key, req.batch_id)
            except (APIError, AuthAPIError):
                continue

            # Always update expires_at if we got a fresher value
            if result.get("expires_at") and not req.expires_at:
                db.update_expires_at(self._cfg.db_path, req.batch_id, result["expires_at"])

            if result["status"] == "ended":
                counts = result["counts"]
                if counts["errored"] > 0 and counts["succeeded"] == 0:
                    final_status = "failed"
                elif counts["expired"] > 0 and counts["succeeded"] == 0:
                    final_status = "expired"
                else:
                    final_status = "completed"

                db.update_request_status(
                    self._cfg.db_path,
                    req.batch_id,
                    final_status,
                    completed_at=datetime.now(tz=timezone.utc).isoformat(),
                )
                updated = db.get_request_by_batch_id(self._cfg.db_path, req.batch_id)
                if updated:
                    self._requests[req.batch_id] = updated
                    self.call_from_thread(
                        self.query_one(RequestTable).refresh_row,
                        req.batch_id,
                        final_status,
                        updated.is_read,
                        updated.estimated_cost,
                    )

        self.call_from_thread(self._update_header)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_request_table_row_selected(self, event: RequestTable.RowSelected) -> None:
        """Update detail pane when cursor moves."""
        batch_id = event.batch_id
        req = self._requests.get(batch_id)
        responses = self._responses_cache.get(batch_id, [])
        if not responses and req and req.status == "completed":
            responses = db.get_responses(self._cfg.db_path, req.id)
            self._responses_cache[batch_id] = responses
        self.query_one(DetailPane).update_request(req, responses, preview_lines=5)

    def on_data_table_row_selected(self, event) -> None:
        """Enter key on a DataTable row → open the response."""
        self.action_open_response()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_refresh(self) -> None:
        self._load_requests()
        self._update_header()
        self.notify("Refreshed")

    def action_copy_id(self) -> None:
        batch_id = self.query_one(RequestTable).get_selected_batch_id()
        if not batch_id:
            return
        try:
            import pyperclip
            pyperclip.copy(batch_id)
            self.notify(f"Copied: {batch_id}")
        except Exception:
            self.notify(f"Batch ID: {batch_id}", title="Copy (no clipboard)")

    def action_open_response(self) -> None:
        batch_id = self.query_one(RequestTable).get_selected_batch_id()
        if not batch_id:
            return
        req = self._requests.get(batch_id)
        if not req or req.status != "completed":
            self.notify("No completed response for this request.", severity="warning")
            return

        responses = self._responses_cache.get(batch_id)
        if not responses:
            responses = db.get_responses(self._cfg.db_path, req.id)
            if not responses:
                try:
                    api_key = get_api_key()
                    results = get_results(api_key, req.batch_id)
                    total_in = total_out = 0
                    for br in results:
                        if br.status == "succeeded" and br.content:
                            cost = estimate_cost(req.model, br.input_tokens or 0, br.output_tokens or 0)
                            db.save_response(
                                self._cfg.db_path, req.id, br.content,
                                custom_id=br.custom_id,
                                input_tokens=br.input_tokens,
                                output_tokens=br.output_tokens,
                                estimated_cost=cost,
                            )
                            total_in += br.input_tokens or 0
                            total_out += br.output_tokens or 0
                    total_cost = estimate_cost(req.model, total_in, total_out)
                    db.update_request_status(
                        self._cfg.db_path, req.batch_id, "completed",
                        completed_at=req.completed_at,
                        input_tokens=total_in,
                        output_tokens=total_out,
                        estimated_cost=total_cost,
                    )
                    responses = db.get_responses(self._cfg.db_path, req.id)
                except Exception as e:
                    self.notify(f"Failed to fetch: {e}", severity="error")
                    return
            self._responses_cache[batch_id] = responses

        if not responses:
            self.notify("No response content available.", severity="warning")
            return

        content = responses[0].content
        db.mark_as_read(self._cfg.db_path, batch_id)
        req2 = db.get_request_by_batch_id(self._cfg.db_path, batch_id)
        if req2:
            self._requests[batch_id] = req2
            self.query_one(RequestTable).refresh_row(
                batch_id, req2.status, req2.is_read, req2.estimated_cost
            )

        pager = os.environ.get("PAGER", "less")
        with self.suspend():
            try:
                subprocess.run([pager], input=content.encode(), check=False)
            except FileNotFoundError:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                ) as f:
                    f.write(content)
                    fname = f.name
                subprocess.run(["cat", fname], check=False)
                os.unlink(fname)

    def action_delete_request(self) -> None:
        batch_id = self.query_one(RequestTable).get_selected_batch_id()
        if not batch_id:
            return

        def _do_delete(confirmed: bool) -> None:
            if confirmed:
                db.delete_request(self._cfg.db_path, batch_id)
                self._requests.pop(batch_id, None)
                self._responses_cache.pop(batch_id, None)
                self._load_requests()
                self.notify(f"Deleted {batch_id[:16]}..")

        self.push_screen(ConfirmScreen(f"Delete {batch_id[:16]}..?"), _do_delete)

    def action_new_request(self) -> None:
        cfg = self._cfg
        skills = skills_mod.list_skills(cfg.skills_dir)

        def _submit(params: Optional[NewBatchParams]) -> None:
            if not params:
                return
            try:
                api_key = get_api_key()
            except AuthError as e:
                self.notify(str(e), severity="error")
                return

            system_text: Optional[str] = None
            if params.skill_name:
                system_text = skills_mod.get_skill(cfg.skills_dir, params.skill_name)

            try:
                request_obj = build_single_request(
                    prompt=params.prompt,
                    model=params.model,
                    max_tokens=cfg.max_tokens,
                    system_prompt=system_text,
                    files=params.file_paths or None,
                )
                result = submit_batch(api_key, [request_obj])
                batch_id = result["batch_id"]
                expires_at = result["expires_at"]
            except Exception as e:
                self.notify(str(e), severity="error")
                return

            file_name = ", ".join(p.name for p in params.file_paths) if params.file_paths else None
            db.save_request(
                db_path=cfg.db_path,
                batch_id=batch_id,
                model=params.model,
                user_prompt=params.prompt,
                max_tokens=cfg.max_tokens,
                custom_id=request_obj["custom_id"],
                system_prompt=system_text,
                skill_name=params.skill_name,
                file_name=file_name,
                tag=params.tag,
                expires_at=expires_at,
            )
            req = db.get_request_by_batch_id(cfg.db_path, batch_id)
            if req:
                self._requests[batch_id] = req
                self.query_one(RequestTable).add_request(req)
            self.notify(f"Submitted: {batch_id[:16]}..")

        self.push_screen(NewRequestScreen(cfg, skills), _submit)

    def action_search(self) -> None:
        def _do_search(query: Optional[str]) -> None:
            self._load_requests(query=query)

        self.push_screen(SearchScreen(), _do_search)

    def action_toggle_prompt(self) -> None:
        table = self.query_one(RequestTable)
        table.toggle_prompt(list(self._requests.values()))
