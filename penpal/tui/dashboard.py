"""DataTable widget for the request list."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable
from textual.app import ComposeResult

from penpal.cost import format_cost
from penpal.models import Request


def _ago(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
        diff = datetime.now(tz=timezone.utc) - dt
        s = int(diff.total_seconds())
        if s < 60:
            return f"{s}s ago"
        if s < 3600:
            return f"{s // 60}m ago"
        if s < 86400:
            return f"{s // 3600}h ago"
        return f"{s // 86400}d ago"
    except Exception:
        return dt_str


def _model_short(model: str) -> str:
    parts = model.split("-")
    return parts[1] if len(parts) > 1 else model


def _status_cell(status: str, is_read: bool) -> str:
    if status == "completed":
        icon = "✓ done"
        return f"[bold green]{icon}[/bold green]" if not is_read else f"[dim green]{icon}[/dim green]"
    if status == "processing":
        return "[yellow]⏳ pending[/yellow]"
    if status == "failed":
        return "[red]✗ failed[/red]"
    if status == "expired":
        return "[dim]⌛ expired[/dim]"
    if status == "cancelled":
        return "[dim]⊘ cancelled[/dim]"
    return status


def _file_count(file_name: Optional[str]) -> str:
    if not file_name:
        return "—"
    return str(len([f for f in file_name.split(",") if f.strip()]))


def _expires_cell(expires_at: Optional[str]) -> str:
    if not expires_at:
        return "—"
    try:
        dt = datetime.fromisoformat(expires_at).replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        diff = dt - now
        total = int(diff.total_seconds())
        if total <= 0:
            return "[dim]expired[/dim]"
        if total < 3600:
            return f"[yellow]{total // 60}m[/yellow]"
        if total < 86400:
            return f"{total // 3600}h {(total % 3600) // 60}m"
        # Show absolute date once > 24h away
        return dt.strftime("%b %d %H:%M")
    except Exception:
        return expires_at


def _prompt_preview(user_prompt: str) -> str:
    stripped = user_prompt.replace("\n", " ").strip()
    if len(stripped) <= 30:
        return stripped
    return stripped[:30] + ".."


# Fixed column keys (always present)
_FIXED_COLS = [
    ("time",     "Time"),
    ("model",    "Model"),
    ("status",   "Status"),
    ("batch_id", "Batch ID"),
    ("tag",      "Tag"),
    ("files",    "Files"),
    ("skill",    "Skill"),
    ("expires",  "Expires"),
    ("cost",     "Cost"),
]
# Optional column
_PROMPT_COL = ("prompt", "Prompt")


class RequestTable(Widget):
    """Scrollable DataTable of all batch requests."""

    class RowSelected(Message):
        def __init__(self, batch_id: str) -> None:
            super().__init__()
            self.batch_id = batch_id

    _row_keys: dict[str, object]
    _show_prompt: bool

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._row_keys = {}
        self._show_prompt = False

    def compose(self) -> ComposeResult:
        yield DataTable(cursor_type="row", zebra_stripes=True)

    def on_mount(self) -> None:
        self._rebuild_columns()

    def _rebuild_columns(self) -> None:
        table = self.query_one(DataTable)
        table.clear(columns=True)
        self._row_keys = {}
        cols = _FIXED_COLS + ([_PROMPT_COL] if self._show_prompt else [])
        for key, label in cols:
            table.add_column(label, key=key)

    def toggle_prompt(self, requests: list[Request]) -> None:
        self._show_prompt = not self._show_prompt
        self._rebuild_columns()
        for req in requests:
            self._add_row(self.query_one(DataTable), req)

    def populate(self, requests: list[Request]) -> None:
        table = self.query_one(DataTable)
        table.clear()
        self._row_keys = {}
        for req in requests:
            self._add_row(table, req)

    def _row_values(self, req: Request) -> list:
        values = [
            _ago(req.created_at),
            _model_short(req.model),
            _status_cell(req.status, req.is_read),
            req.batch_id,                              # full ID
            req.tag or "—",
            _file_count(req.file_name),
            req.skill_name or "—",
            _expires_cell(req.expires_at),
            format_cost(req.estimated_cost or 0.0),
        ]
        if self._show_prompt:
            values.append(_prompt_preview(req.user_prompt))
        return values

    def _add_row(self, table: DataTable, req: Request) -> None:
        table.add_row(*self._row_values(req), key=req.batch_id)
        self._row_keys[req.batch_id] = req.batch_id

    def add_request(self, req: Request) -> None:
        table = self.query_one(DataTable)
        if req.batch_id not in self._row_keys:
            self._add_row(table, req)

    def refresh_row(self, batch_id: str, status: str, is_read: bool, cost: Optional[float]) -> None:
        if batch_id not in self._row_keys:
            return
        try:
            table = self.query_one(DataTable)
            table.update_cell(batch_id, "status", _status_cell(status, is_read))
            table.update_cell(batch_id, "cost", format_cost(cost or 0.0))
        except Exception:
            pass

    def get_selected_batch_id(self) -> Optional[str]:
        table = self.query_one(DataTable)
        if table.cursor_row < 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key((table.cursor_row, 0)).row_key
            return str(row_key.value) if row_key.value else None
        except Exception:
            return None

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key and event.row_key.value:
            self.post_message(self.RowSelected(str(event.row_key.value)))
