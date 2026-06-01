---
name: hermes-board
description: Use when managing the Slack Kanban board (the /board command) in natural language — creating, moving, assigning, completing, or decomposing task cards. Covers the column lifecycle and how to control task decomposition so board changes are predictable.
---

# Hermes Slack Board

`/board` opens a Block Kit Kanban board backed by Hermes Kanban. Manage it with the `kanban_*` tools (`kanban_create`, `kanban_show`, `kanban_complete`, `kanban_block`, `kanban_unblock`, `kanban_comment`, `kanban_link`). Always use these tools — never shell out to a `hermes` CLI or `sqlite3`.

Respond in the language the user is using.

## Columns (status lifecycle)

`triage → todo → ready → running (In Progress) → review → done`, plus `blocked`.

- You create cards only in `triage`, `todo`, or `ready`.
- `running` and `review` are driven by the orchestrator as tasks execute and await approval — never set them by hand.
- `blocked` and `done` are reached by moving an existing card.

## Respect the requested column exactly

When the user lists cards with explicit columns, create each card in EXACTLY that column. Do NOT promote `todo` to `ready`, and do NOT add an assignee unless the user named one. One card request → one `kanban_create` with only the title, the requested status, and (if given) the assignee. This keeps the board predictable instead of reshuffling what the user asked for.

## Triage is the decomposition lane

A card placed in `triage` is decomposed into a tree of sub-tasks (one task fans out into several) and then moves to `todo`. Cards created in `todo` or `ready` are NOT decomposed — they stay exactly as created.

- In **Auto** orchestration (the default), the orchestrator decomposes a `triage` card on its own within a minute or so.
- In **Manual** orchestration (`kanban.auto_decompose: false`, or the Auto/Manual pill set to Manual), a `triage` card waits until someone clicks **⚗ Decompose** or runs `hermes kanban decompose`.

Use this deliberately:

- The user wants a fixed, clean set of cards → create them all in `todo`/`ready`. Nothing decomposes.
- The user wants one larger task broken into steps → put that one in `triage`. It fans out into sub-tasks (and, in Auto mode, workers may start running them).

If the user gives a mixed list (some `todo`/`ready`, one `triage`), honor it as written: the `todo`/`ready` cards stay put and only the `triage` card decomposes.

## Moving, blocking, completing

- Block with `kanban_block` (and an optional reason) / resume with `kanban_unblock`.
- Mark finished work `done` with `kanban_complete`.
- Add context with `kanban_comment`. Approve review-stage work to advance it.

Keep every reply short and concrete: say what you created or moved and where, not a narration of the tool calls.
