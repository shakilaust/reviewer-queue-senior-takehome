# Submission

## Summary of changes

Fixed four workflow-correctness bugs in the backend and two in the frontend, then built out a substantially richer reviewer UI: sidebar stats, search, filter tabs, urgency badges, age/SLA indicators, a richer detail panel with SLA banner, related signals, notes thread, and a styled action bar. Expanded the test suite from 2 smoke tests to 22 tests across two layers.

## Bugs fixed

**Backend (`backend/app/main.py`)**

1. **Active queue included terminal items** — `list_review_items` filtered out only `approved`, leaving `rejected` and `escalated` items in the active queue. Fixed to exclude all three terminal statuses.

2. **Queue sort order was wrong** — items were sorted newest-first by `submitted_at` only, ignoring risk level and customer tier entirely. Fixed with a tuple sort key `(RISK_ORDER, TIER_ORDER, submitted_at)` where `RISK_ORDER = {"high": 0, "medium": 1, "low": 2}` and `TIER_ORDER = {"priority": 0, "standard": 1}` — lower value sorts first, so high-risk priority items surface at the top and older items break ties within the same bucket.

3. **`claim` allowed re-claiming in-review items** — the guard only blocked terminal statuses, so an `in_review` item could be re-claimed (and its `assigned_reviewer` overwritten). Fixed: claim now requires `status == "unassigned"`.

4. **`approve/reject/escalate` accepted unassigned items** — the guard only blocked items already `approved`, so `unassigned` items could be approved or rejected directly without ever being claimed. Also, `rejected` and `escalated` items were not blocked from further actions. Fixed: both guards now enforce the full state machine (`in_review` required, all terminals blocked).

**Frontend (`frontend/src/App.vue`)**

5. **All four action buttons rendered for every item** — a reviewer could click "Approve" on a terminal or unassigned item and receive an opaque error. Fixed with a `v-if/v-else-if/v-else` block directly on `selectedItem.status`.

6. **Terminal items stayed in the queue after action** — approving, rejecting, or escalating an item left it in the left-hand queue list. Fixed: after a terminal action the item is filtered out of `items` locally and `selectedId` is set to `items.value[0]?.id` so the reviewer lands on the highest-urgency remaining item.

## Product/UX decisions

**Reviewer avatar** — replaced the "Signed in as alex" text pill with a 36 px avatar circle showing initials (AX). Reduces header clutter while keeping identity visible.

**Sidebar stats row** — three cards above the queue list show High risk count, Priority count, and Total open. Updates reactively as items are actioned. Gives a reviewer instant situational awareness without scrolling.

**Search and filter tabs** — a search input filters queue items by title in real time. Four tabs (All / Unassigned / Mine / Priority) let a reviewer narrow to their workload. Filters compose with search. Stats remain based on the full active queue so they always reflect true totals.

**Queue item density** — each row now shows: title + submission time (top), risk and tier badges (middle), age + assignee (bottom). Replaces plain text with scannable information so a reviewer can triage without opening every item. `timeAgo()` converts ISO dates to human-readable age ("2d ago", "3h 15m").

**Colour-coded urgency badges** — red/amber/green for risk level, blue/grey for customer tier. Directly shortens the time to answer "what do I work on next?" Badge colours reuse the existing palette (error red, info blue, neutral grey).

**Detail panel header** — replaced the plain title + status pill with a richer header: item ID (eyebrow), inline HIGH RISK and tier badges, Flag and Share icon buttons. The status pill is removed; status is communicated through the action bar instead.

**SLA breach banner** — shown only for `high` risk + `unassigned` items. Red banner with a "Claim now" CTA makes the urgency unmissable and provides a one-click shortcut to the most time-critical action. Disappears automatically once the item is claimed.

**"Assign to me" in facts grid** — the Assignee cell shows a small inline button for unassigned items. Provides a second entry point for claiming without requiring the reviewer to scroll to the action bar. Disappears once assigned.

**Related signals section** — shown only for high-risk items. Two hardcoded signal rows (prototype — explained with `TAKEHOME` comment). In production these would come from a `/review-items/:id/signals` endpoint. Gives reviewers context about why an item is high-risk without leaving the tool.

**Notes thread with avatars** — replaced the bare `notes_count` text with a threaded notes section: per-note avatars, author, timestamp, and text. Hardcoded for RV-1024 (prototype — `TAKEHOME` comment explains production shape). Other items show "No notes on this item yet." The `notes_count` from seed data is preserved in the section header.

**Richer action bar** — plain text buttons replaced with styled `action-btn` variants. For `unassigned`: "✦ Claim & start review" (dark primary), "↑ Escalate", "✕ Dismiss". For `in_review`: Approve (primary), Reject (danger), Escalate (default). Visual hierarchy signals the recommended action.

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

- **No persistence** — ITEMS is an in-memory list; server restart resets all state. Acceptable per the brief, but means `/dev/reset` is the only recovery path.
- **Hardcoded notes and signals** — mock notes exist only for RV-1024; signals show for all high-risk items regardless of content. Both are clearly marked with `TAKEHOME` comments. The production shape (API endpoint + response field) is described in each comment.
- **No frontend tests** — the action-button branching and filter logic are simple enough that I judged backend coverage sufficient for this timebox. Component tests asserting rendered buttons per status and filtered item counts would be the obvious next additions.
- **Single reviewer identity** — `alex` is hardcoded as the brief specifies, so there is no ownership check (any reviewer can act on any item regardless of who claimed it).
- **Escalate/Reject on unassigned** — the action bar for `unassigned` items includes Escalate and Dismiss buttons per the task spec, but the backend correctly returns 409 for these (only `claim` is valid on unassigned). The buttons are present as a UI prototype; a future tightening would either hide them or pre-validate client-side.
- **No optimistic rollback** — if an API call fails, the frontend shows an error banner but no local state has been mutated (mutation happens after the response), so no rollback is needed in practice.

## Files changed and why

| File | Why |
|---|---|
| `backend/app/main.py` | All four workflow-correctness fixes; `TERMINAL_STATUSES` module-level constant; `RISK_ORDER`/`TIER_ORDER` locals inside `list_review_items` |
| `backend/requirements.txt` | Added `httpx==0.28.1` for ASGI test client |
| `backend/tests/test_smoke.py` | Expanded from 2 to 22 tests: 12 Python function-call + 8 HTTP-level; `reset_state` autouse fixture |
| `frontend/src/App.vue` | All frontend changes: workflow guards, stats row, search/filter, urgency badges, time/age lines, detail header, SLA banner, assign-to-me, related signals, notes thread, richer action bar; all component styles in `<style scoped>` |
| `frontend/src/styles.css` | Removed `.reviewer` pill rule and `.actions button` rules superseded by scoped styles |

## AI assistance used

Claude Code (claude-sonnet-4-6) was used throughout:

- **Bug identification**: asked the assistant to audit the codebase against the README spec. It correctly identified all six bugs.
- **Code generation**: the assistant wrote all edits across all five changed files. I reviewed each diff before accepting.
- **Test assertion bug**: the ordering test initially used `a_key >= b_key`; the assistant caught and fixed this when the test output was shown.
- **Design tasks**: each UI task was specified precisely (exact HTML, exact CSS); the assistant applied the changes and I verified TypeScript compiled clean and the behaviour matched the spec.
- **Review**: I read every changed line. The final logic, design decisions, and tradeoffs are mine.
