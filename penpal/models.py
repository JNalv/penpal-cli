"""Data classes for Penpal domain objects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Request:
    id: int
    batch_id: str
    custom_id: Optional[str]
    model: str
    system_prompt: Optional[str]
    skill_name: Optional[str]
    user_prompt: str
    file_name: Optional[str]
    tag: Optional[str]
    max_tokens: int
    status: str  # processing | completed | failed | expired | cancelled
    is_read: bool
    is_multi: bool
    request_count: int
    created_at: str
    completed_at: Optional[str]
    expires_at: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost: Optional[float]


@dataclass
class Response:
    id: int
    request_id: int
    custom_id: Optional[str]
    file_name: Optional[str]
    content: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost: Optional[float]
    created_at: str


@dataclass
class BatchResult:
    custom_id: str
    status: str  # succeeded | errored | expired | canceled
    content: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    error: Optional[str] = None


@dataclass
class CostSummary:
    total: float
    by_model: dict[str, float]
    request_count: int
    total_input_tokens: int = 0
    total_output_tokens: int = 0
