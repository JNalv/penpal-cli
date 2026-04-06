"""Detail pane widget — shows a preview of the selected request's response."""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from penpal.models import Request, Response


class DetailPane(Widget):
    """Bottom panel showing a preview of the selected request."""

    DEFAULT_CSS = ""

    def compose(self) -> ComposeResult:
        yield Static("", id="detail-header")
        yield Static("", id="detail-content")
        yield Static("[dim][Enter] open in pager (press q to exit)  [c] copy batch ID[/dim]", id="detail-footer")

    def update_request(
        self,
        req: Optional[Request],
        responses: list[Response],
        preview_lines: int = 8,
    ) -> None:
        header = self.query_one("#detail-header", Static)
        content_widget = self.query_one("#detail-content", Static)

        if req is None:
            header.update("[dim]No request selected[/dim]")
            content_widget.update("")
            return

        model_short = req.model.split("-")[1] if "-" in req.model else req.model
        tag_part = f" — {req.tag}" if req.tag else ""
        header.update(f"[bold]Preview: {req.batch_id[:12]}.. ({model_short}){tag_part}[/bold]")

        if req.status == "processing":
            content_widget.update("[yellow]⏳ Still processing...[/yellow]")
            return

        if req.status in ("failed", "expired", "cancelled"):
            content_widget.update(f"[red]✗ Batch {req.status}[/red]")
            return

        if not responses:
            content_widget.update("[dim]Response not yet fetched. Press Enter to load.[/dim]")
            return

        if req.is_multi:
            content_widget.update(
                f"[dim]Multi-request batch with {len(responses)} results. Press Enter to view.[/dim]"
            )
            return

        text = responses[0].content
        lines = text.splitlines()
        preview = "\n".join(lines[:preview_lines])
        if len(lines) > preview_lines:
            preview += f"\n[dim]... ({len(lines) - preview_lines} more lines)[/dim]"

        style = "" if req.is_read else "[bold]"
        end_style = "" if req.is_read else "[/bold]"
        content_widget.update(f"{style}{preview}{end_style}")
