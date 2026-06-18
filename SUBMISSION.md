# Submission

## Summary of changes

Fixed four workflow-correctness bugs in the backend and two in the frontend, added colour-coded urgency badges and a context-aware action panel as UX improvements, and expanded the test suite from 2 smoke tests to 22 tests across two layers: direct Python function calls and full HTTP-level tests via `httpx.AsyncClient`.

## Bugs fixed

**Backend (`backend/app/main.py`)**

1. **Active queue included terminal items** — `list_review_items` filtered out only `approved`, leaving `rejected` and `escalated` items in the active queue. Fixed to exclude all three terminal statuses.

2. **Queue sort order was wrong** — items were sorted newest-first by `submitted_at` only, ignoring risk level and customer tier entirely. Fixed with a tuple sort key `(RISK_ORDER, TIER_ORDER, submitted_at)` where `RISK_ORDER = {"high": 0, "medium": 1, "low": 2}` and `TIER_ORDER = {"priority": 0, "standard": 1}` — lower value sorts first, so high-risk priority items surface at the top and older items break ties within the same bucket.

3. **`claim` allowed re-claiming in-review items** — the guard only blocked terminal statuses, so an `in_review` item could be re-claimed (and its `assigned_reviewer` overwritten). Fixed: claim now requires `status == "unassigned"`.

4. **`approve/reject/escalate` accepted unassigned items** — the guard only blocked items already `approved`, so `unassigned` items could be approved or rejected directly without ever being claimed. Also, `rejected` and `escalated` items were not blocked from further actions. Fixed: both guards now enforce the full state machine (`in_review` required, all terminals blocked).

**Frontend (`frontend/src/App.vue`)**

5. **All four action buttons rendered for every item** — a reviewer could click "Approve" on a terminal or unassigned item and receive an opaque error. The backend correctly rejected these, but the UI offered no indication of what was allowed. Fixed with a `v-if/v-else-if/v-else` block directly on `selectedItem.status` — no intermediate computed needed (see UX decisions).

6. **Terminal items stayed in the queue after action** — approving, rejecting, or escalating an item left it in the left-hand queue list. The active queue is supposed to exclude terminal items. Fixed: after a terminal action the item is filtered out of `items` locally and `selectedId` is set to `items.value[0]?.id` so the reviewer lands on the highest-urgency remaining item.

## Product/UX decisions

**Colour-coded urgency badges in the sidebar** (`App.vue`): the plain-text `risk · tier` line in each queue row is replaced with two pill badges — red/amber/green for risk level, blue/grey for customer tier. Reviewers can scan the entire queue at a glance and immediately spot high-risk priority items without reading every row. This directly shortens the time to answer "what do I work on next?" The badge colours reuse the existing palette from `styles.css` (error red, info blue, neutral grey) so nothing looks out of place.

**Context-aware action buttons** (`App.vue`): instead of always showing all four buttons and letting the backend reject invalid calls, the action panel now shows only the actions that are valid for the current item's state:

- `unassigned` → only **Claim**
- `in_review` → only **Approve**, **Reject**, **Escalate**
- terminal → text notice "This item is `<status>`. No further actions are available."

This directly answers the reviewer's question "what can I do with this item right now?" without requiring them to try an action and interpret an error. The tradeoff is that the UI now encodes state-machine knowledge in two places (frontend and backend); I kept it acceptable by making the backend the authoritative source and the frontend purely presentational.

I chose this over leaving all buttons visible and disabling them because a disabled button with no explanation is nearly as confusing as an error message. The implementation uses `v-if/v-else-if/v-else` on `selectedItem.status` directly in the template — no `allowedActions` computed — keeping the logic flat and easy to read.

## Tests added

All 20 new tests are in `backend/tests/test_smoke.py`. The `reset_state` autouse fixture calls `asyncio.run(reset_items())` before each test so they are fully independent.

**Python function-call layer** (12 tests — call `apply_action`, `list_review_items` directly):

| Test | What it covers |
|---|---|
| `test_active_queue_excludes_all_terminal_statuses` | All three terminal statuses absent from active queue |
| `test_all_items_returned_when_active_only_false` | `active_only=False` still surfaces terminals |
| `test_queue_ordered_by_risk_then_tier_then_age` | Consecutive items satisfy the sort invariant |
| `test_claim_unassigned_item_succeeds` | Happy path: status → `in_review`, reviewer recorded |
| `test_claim_in_review_item_is_rejected` | 409 on re-claim |
| `test_claim_terminal_item_is_rejected` | 409 on claiming already-approved item |
| `test_approve_in_review_item_succeeds` | Happy path approve |
| `test_reject_in_review_item_succeeds` | Happy path reject |
| `test_escalate_in_review_item_succeeds` | Happy path escalate |
| `test_approve_unassigned_item_is_rejected` | 409 on approving without claiming first |
| `test_terminal_item_blocks_all_further_actions` | 409 for approve/reject/escalate on all three terminal statuses |
| `test_full_claim_then_approve_flow` | End-to-end: claim then approve, reviewer preserved |

**HTTP layer** (8 tests — `httpx.AsyncClient` with `ASGITransport`, exercises routing, request parsing, and status codes end-to-end):

| Test | What it covers |
|---|---|
| `test_claim_unassigned_succeeds` | POST claim → 200, `in_review`, reviewer `alex` |
| `test_claim_in_review_returns_409` | Claim twice → second POST returns 409 |
| `test_claim_terminal_returns_409` | Claim already-approved RV-1029 → 409 |
| `test_approve_in_review_succeeds` | Claim then approve → 200, `approved` |
| `test_approve_unassigned_returns_409` | Approve without claiming → 409 |
| `test_approve_already_approved_returns_409` | Claim, approve, approve again → 409 |
| `test_queue_excludes_terminal_items` | GET `/review-items` → RV-1029, RV-1033, RV-1034 absent |
| `test_queue_sorts_high_risk_first` | GET `/review-items` → first item is `high`, no `high` appears after `medium`/`low` |

All 22 tests pass (`pytest -v`).

## Known gaps

- **No persistence** — ITEMS is an in-memory list; server restart resets all state. Acceptable per the brief, but means the `/dev/reset` endpoint is the only recovery path.
- **No frontend tests** — the action-button branching logic is simple enough that I judged backend coverage sufficient for this timebox. A component test asserting which buttons render per status would be the obvious next addition.
- **Single reviewer identity** — `alex` is hardcoded as the brief specifies, so there is no ownership check (any reviewer can act on any item regardless of who claimed it).
- **No optimistic rollback** — if the API call fails after an action, the frontend shows an error banner but does not undo any local state change. In practice no local state is mutated before the response arrives, so this is safe for the current implementation.
- **Sort applies to the full list including `active_only=False`** — the spec only defines ordering for the active queue, but the sort now runs unconditionally. Not harmful, just untested for the terminal-items case.

## Files changed and why

| File | Why |
|---|---|
| `backend/app/main.py` | All four workflow-correctness fixes; `TERMINAL_STATUSES` added as a module-level constant after `ITEMS`; `RISK_ORDER` and `TIER_ORDER` defined as local variables inside `list_review_items` |
| `frontend/src/App.vue` | Replaced static button block with `v-if/v-else-if/v-else` on `selectedItem.status`; `TERMINAL_STATUSES` is a `Set` for O(1) lookup; `performAction` removes terminal items from the queue list and jumps to `items[0]`; colour-coded urgency badges in sidebar; all styles in `<style scoped>` |
| `backend/requirements.txt` | Added `httpx==0.28.1` for ASGI test client |
| `backend/tests/test_smoke.py` | Expanded from 2 to 22 tests: 12 Python function-call tests + 8 HTTP-level tests via `httpx.AsyncClient`/`ASGITransport`; `reset_state` autouse fixture resets seed state before each test |

## AI assistance used

Claude Code (claude-sonnet-4-6) was used throughout:

- **Bug identification**: I described the codebase and asked the assistant to identify all workflow-correctness violations against the README spec. It correctly identified all six bugs.
- **Code generation**: the assistant wrote all edits to `main.py`, `App.vue`, and `test_smoke.py`. I reviewed each diff before accepting.
- **Test assertion bug**: the ordering test initially used `a_key >= b_key` which failed because the date component is ascending. The assistant caught and fixed this when the test run output was shown.
- **Review**: I read every changed line and cross-checked the state-machine logic against the README rules before accepting. The final logic and design decisions are mine.
