import asyncio

import pytest
from fastapi import HTTPException

from app.main import ActionRequest, apply_action, health, list_review_items, reset_items


def run_async(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def reset():
    run_async(reset_items())
    yield
    run_async(reset_items())


def test_health_check() -> None:
    assert run_async(health()) == {"status": "ok"}


def test_review_items_endpoint_returns_seed_data() -> None:
    response = run_async(list_review_items())
    assert len(response["items"]) > 0


# --- Active queue filter ---

def test_active_queue_excludes_all_terminal_statuses() -> None:
    response = run_async(list_review_items(active_only=True))
    statuses = {item["status"] for item in response["items"]}
    assert not statuses.intersection({"approved", "rejected", "escalated"})


def test_all_items_returned_when_active_only_false() -> None:
    response = run_async(list_review_items(active_only=False))
    statuses = {item["status"] for item in response["items"]}
    assert "approved" in statuses or "rejected" in statuses or "escalated" in statuses


# --- Queue ordering ---

def test_queue_ordered_by_risk_then_tier_then_age() -> None:
    response = run_async(list_review_items(active_only=True))
    items = response["items"]

    RISK = {"high": 2, "medium": 1, "low": 0}
    TIER = {"priority": 1, "standard": 0}

    # Sort key used by the backend: (-risk, -tier, submitted_at asc).
    # Consecutive items must be non-decreasing in that key.
    for i in range(len(items) - 1):
        a, b = items[i], items[i + 1]
        a_key = (-RISK[a["risk_level"]], -TIER[a["customer_tier"]], a["submitted_at"])
        b_key = (-RISK[b["risk_level"]], -TIER[b["customer_tier"]], b["submitted_at"])
        assert a_key <= b_key, f"Item {a['id']} ranked above {b['id']} but has lower urgency"


# --- Claim ---

def test_claim_unassigned_item_succeeds() -> None:
    response = run_async(apply_action("RV-1024", ActionRequest(action="claim")))
    assert response["item"]["status"] == "in_review"
    assert response["item"]["assigned_reviewer"] == "alex"


def test_claim_in_review_item_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        run_async(apply_action("RV-1027", ActionRequest(action="claim")))
    assert exc.value.status_code == 409


def test_claim_terminal_item_is_rejected() -> None:
    # RV-1029 is already approved in seed data
    with pytest.raises(HTTPException) as exc:
        run_async(apply_action("RV-1029", ActionRequest(action="claim")))
    assert exc.value.status_code == 409


# --- Approve / reject / escalate ---

def test_approve_in_review_item_succeeds() -> None:
    response = run_async(apply_action("RV-1030", ActionRequest(action="approve")))
    assert response["item"]["status"] == "approved"


def test_reject_in_review_item_succeeds() -> None:
    response = run_async(apply_action("RV-1027", ActionRequest(action="reject")))
    assert response["item"]["status"] == "rejected"


def test_escalate_in_review_item_succeeds() -> None:
    response = run_async(apply_action("RV-1028", ActionRequest(action="escalate")))
    assert response["item"]["status"] == "escalated"


def test_approve_unassigned_item_is_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        run_async(apply_action("RV-1024", ActionRequest(action="approve")))
    assert exc.value.status_code == 409


def test_terminal_item_blocks_all_further_actions() -> None:
    # RV-1029 approved, RV-1033 escalated, RV-1034 rejected in seed data
    for item_id, action in [
        ("RV-1029", "approve"),
        ("RV-1029", "reject"),
        ("RV-1029", "escalate"),
        ("RV-1033", "approve"),
        ("RV-1034", "reject"),
    ]:
        with pytest.raises(HTTPException) as exc:
            run_async(apply_action(item_id, ActionRequest(action=action)))
        assert exc.value.status_code == 409, f"{item_id} / {action} should be blocked"


def test_full_claim_then_approve_flow() -> None:
    run_async(apply_action("RV-1024", ActionRequest(action="claim")))
    response = run_async(apply_action("RV-1024", ActionRequest(action="approve")))
    assert response["item"]["status"] == "approved"
    assert response["item"]["assigned_reviewer"] == "alex"
