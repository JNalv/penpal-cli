"""Tests for db.py"""
import pytest
import tempfile
from pathlib import Path

from penpal import db
from penpal.db import init_db


@pytest.fixture
def tmp_db(tmp_path):
    p = tmp_path / "test.db"
    init_db(p)
    return p


def test_save_and_retrieve_request(tmp_db):
    rid = db.save_request(
        tmp_db, batch_id="batch_001", model="claude-sonnet-4-20250514",
        user_prompt="Hello", max_tokens=100, tag="test"
    )
    assert rid == 1
    req = db.get_request_by_batch_id(tmp_db, "batch_001")
    assert req is not None
    assert req.batch_id == "batch_001"
    assert req.status == "processing"
    assert req.tag == "test"
    assert not req.is_read


def test_prefix_lookup(tmp_db):
    db.save_request(tmp_db, batch_id="msgbatch_abc123", model="m", user_prompt="p", max_tokens=10)
    req = db.get_request_by_batch_id(tmp_db, "msgbatch_abc")
    assert req is not None


def test_update_status(tmp_db):
    db.save_request(tmp_db, batch_id="b1", model="m", user_prompt="p", max_tokens=10)
    db.update_request_status(tmp_db, "b1", "completed", completed_at="2024-01-01T00:00:00",
                              input_tokens=100, output_tokens=50, estimated_cost=0.01)
    req = db.get_request_by_batch_id(tmp_db, "b1")
    assert req.status == "completed"
    assert req.input_tokens == 100
    assert req.estimated_cost == pytest.approx(0.01)


def test_save_and_get_response(tmp_db):
    rid = db.save_request(tmp_db, batch_id="b1", model="m", user_prompt="p", max_tokens=10)
    db.save_response(tmp_db, request_id=rid, content="Hello world", input_tokens=5, output_tokens=10)
    responses = db.get_responses(tmp_db, rid)
    assert len(responses) == 1
    assert responses[0].content == "Hello world"


def test_mark_as_read(tmp_db):
    db.save_request(tmp_db, batch_id="b1", model="m", user_prompt="p", max_tokens=10)
    db.mark_as_read(tmp_db, "b1")
    req = db.get_request_by_batch_id(tmp_db, "b1")
    assert req.is_read


def test_get_pending(tmp_db):
    db.save_request(tmp_db, batch_id="b1", model="m", user_prompt="p1", max_tokens=10)
    db.save_request(tmp_db, batch_id="b2", model="m", user_prompt="p2", max_tokens=10)
    db.update_request_status(tmp_db, "b2", "completed")
    pending = db.get_pending_requests(tmp_db)
    assert len(pending) == 1
    assert pending[0].batch_id == "b1"


def test_delete_request(tmp_db):
    rid = db.save_request(tmp_db, batch_id="b1", model="m", user_prompt="p", max_tokens=10)
    db.save_response(tmp_db, request_id=rid, content="content")
    result = db.delete_request(tmp_db, "b1")
    assert result is True
    assert db.get_request_by_batch_id(tmp_db, "b1") is None


def test_cost_summary(tmp_db):
    db.save_request(tmp_db, batch_id="b1", model="m", user_prompt="p", max_tokens=10)
    db.update_request_status(tmp_db, "b1", "completed", estimated_cost=0.50)
    summary = db.get_cost_summary(tmp_db)
    assert summary.total == pytest.approx(0.50)
    assert summary.request_count == 1
