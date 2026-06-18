# Submission

## Summary of changes

Fixed four workflow-correctness bugs in the backend and two in the frontend, added a context-aware action panel as a UX improvement, and expanded the test suite from 2 smoke tests to 14 targeted behavior tests.

## Bugs fixed

**Backend (`backend/app/main.py`)**

1. **Active queue included terminal items** — `list_review_items` filtered out only `approved`, leaving `rejected` and `escalated` items in the active queue. Fixed to exclude all three terminal statuses.

2. **Queue sort order was wrong** — items were sorted newest-first by `submitted_at` only, ignoring risk level and customer tier entirely. Fixed to sort by `(-risk_level, -customer_tier, submitted_at)` so high-urgency items surface first and older items break ties within the same bucket.

3. **`claim` allowed re-claiming in-review items** — the guard only blocked terminal statuses, so an `in_review` item could be re-claimed (and its `assigned_reviewer` overwritten). Fixed: claim now requires `status == "unassigned"`.

4. **`approve/reject/escalate` accepted unassigned items** — the guard only blocked items already `approved`, so `unassigned` items could be approved or rejected directly without ever being claimed. Also, `rejected` and `escalated` items were not blocked from further actions. Fixed: both guards now enforce the full state machine (`in_review` required, all terminals blocked).

**Frontend (`frontend/src/App.vue`)**

5. **All four action buttons rendered for every item** — a reviewer could click "Approve" on a terminal or unassigned item and receive an opaque error. The backend correctly rejected these, but the UI offered no indication of what was allowed. Fixed with a computed `allowedActions` property (see UX decisions).

6. **Terminal items stayed in the queue after action** — approving, rejecting, or escalating an item left it in the left-hand queue list. The active queue is supposed to exclude terminal items. Fixed: after a terminal action the item is removed from `items` locally and focus advances to the next item in queue order.

## Product/UX decisions

**Context-aware action buttons** (`App.vue`): instead of always showing all four buttons and letting the backend reject invalid calls, the action panel now shows only the actions that are valid for the current item's state:

- `unassigned` → only **Claim**
- `in_review` → only **Approve**, **Reject**, **Escalate**
- terminal → text notice "No further actions available — this item is `<status>`."

This directly answers the reviewer's question "what can I do with this item right now?" without requiring them to try an action and interpret an error. The tradeoff is that the UI now encodes state-machine knowledge in two places (frontend and backend); I kept it acceptable by making the backend the authoritative source and the frontend purely presentational.

I chose this over leaving all buttons visible and disabling them because a disabled button with no explanation is nearly as confusing as an error message.

## Tests added

All 12 new tests are in `backend/tests/test_smoke.py`. Each test resets seed data via `reset_items()` using an `autouse` fixture so tests are independent.

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

All 14 tests pass (`pytest -v`).

## Known gaps

- **No persistence** — ITEMS is an in-memory list; server restart resets all state. Acceptable per the brief, but means the `/dev/reset` endpoint is the only recovery path.
- **No frontend tests** — the `allowedActions` logic is simple enough that I judged backend coverage sufficient for this timebox. A component test for the computed property would be the obvious next addition.
- **Single reviewer identity** — `alex` is hardcoded as the brief specifies, so there is no ownership check (any reviewer can act on any item regardless of who claimed it).
- **No optimistic rollback** — if the API call fails after an action, the frontend shows an error banner but does not undo any local state change. In practice no local state is mutated before the response arrives, so this is safe for the current implementation.
- **Sort applies to the full list including `active_only=False`** — the spec only defines ordering for the active queue, but the sort now runs unconditionally. Not harmful, just untested for the terminal-items case.

## Files changed and why

| File | Why |
|---|---|
| `backend/app/main.py` | All four workflow-correctness fixes; added `TERMINAL_STATUSES`, `RISK_ORDER`, `TIER_ORDER` constants at module level so the logic is easy to find and test |
| `frontend/src/App.vue` | Added `allowedActions` computed, updated `performAction` to remove terminal items from queue, replaced static button block with `v-if`-gated buttons |
| `frontend/src/styles.css` | Added `.terminal-notice` style for the "no actions" message |
| `backend/tests/test_smoke.py` | Replaced 2 smoke tests with 14 behavior tests; added `autouse` reset fixture |

## AI assistance used

Claude Code (claude-sonnet-4-6) was used throughout:

- **Bug identification**: I described the codebase and asked the assistant to identify all workflow-correctness violations against the README spec. It correctly identified all six bugs.
- **Code generation**: the assistant wrote all edits to `main.py`, `App.vue`, `styles.css`, and `test_smoke.py`. I reviewed each diff before accepting.
- **Test assertion bug**: the ordering test initially used `a_key >= b_key` which failed because the date component is ascending. The assistant caught and fixed this when the test run output was shown.
- **Review**: I read every changed line and cross-checked the state-machine logic against the README rules before accepting. The final logic and design decisions are mine.
