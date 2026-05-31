# hermes-slack-extension

A CLI install wizard that deterministically adds a **`/board` Kanban board** and a **`/meeting` text meeting room**
to the Slack integration of Hermes Agent (0.15.x). It replaces the non-deterministic skill-based approach, so the
same input always produces the same result. You can step through an interactive TUI prompt by prompt, or run it headless with `--answers-file`.

## What it does

- **`/board`** — Idempotently patches a Kanban board Block Kit handler into Hermes's `gateway/platforms/slack.py`
  and installs the board overlay module.
- **`/meeting`** — Automatically creates per-profile Slack apps (participants) and builds a text-driven meeting room
  by configuring the persona matrix, channel prompts, bot-to-bot wiring, and moderator skill.
- **Slash swap** — Within Slack's 50-command limit on slash commands, it removes two rarely used default commands and
  adds `/board` and `/meeting` (see below). The removed commands don't simply disappear — they still work via `/hermes <command>`.
- **Manifest auto-generation** — It calls the installed Hermes's `hermes slack manifest` directly to build a manifest
  that reflects the command registry of the current version, then applies the swap to it.
  Socket Mode and interactivity are enabled automatically in the manifest, so the user doesn't have to turn them on separately.

## Installation

```bash
# Bootstrap (isolated venv + register hermes-ext)
curl -fsSL <install-remote.sh URL> | bash

# Or directly
pip install git+<repo>
hermes-ext install            # interactive wizard
```

The wizard detects the Hermes root (default `~/.hermes/hermes-agent`), verifies it's a supported version (0.12.0–0.15.1),
then has you select features and walks through them step by step.

```
hermes-ext install \
  --hermes-root ~/.hermes/hermes-agent \
  --answers-file answers.yaml \   # headless (optional)
  --non-interactive \
  --dry-run                       # simulate without making changes (optional)
```

## `/meeting` install flow

When you select the meeting feature, the wizard proceeds in the following order.

1. **Configure meeting profiles** — Accept the default set of 4 (Moderator, Researcher, Developer, Designer) as-is,
   or use a preset/custom option to change names and personas (no LLM inference, fully deterministic).
   - The moderator = the user's **existing base Hermes app** (with `/meeting` added via slash swap).
   - The 3 participants = newly created **minimal-manifest apps** (no slash commands, Socket Mode on).
2. **Capture the App Configuration Token** — Enter the token (+refresh) issued at
   `api.slack.com/apps` → _Your App Configuration Tokens_. A single token creates all apps in the workspace.
   Input is not shown on screen; only a masked confirmation is displayed.
3. **Create participant apps and tokens** — For each profile, create an app via `apps.manifest.create`, then the user manually
   installs it (OAuth) and pastes in the resulting Bot Token and App-Level Token. Tokens are written atomically to each profile's `.env`
   with `0600` permissions; `bot_user_id` is acquired automatically via `auth.test`, and the bot is invited if the channel is public.
4. **Apply to the moderator base app** — If the config token and the base `app_id` are present, apply the swapped manifest via `apps.manifest.update`;
   otherwise, point the user to the manifest file path for manual application.
5. **Wiring** — Write bot-to-bot environment variables to each profile's `.env` (`SLACK_ALLOWED_USERS` including all bots,
   `SLACK_ALLOW_BOTS=mentions`, etc.), render the moderator and participant channel prompts into a staging
   directory, and install the moderator skill to `~/.hermes/skills/hermes-meeting/`.

### Manual steps the user must do directly

The wizard guides you through items that can't be automated (Slack UI/OAuth constraints).

- **Issue an App Configuration Token** — _Your App Configuration Tokens_ at `api.slack.com/apps`.
- **Install each participant app (Install to Workspace)** — Issues a Bot Token (`xoxb-…`) via OAuth.
- **Issue an App-Level Token** — With the `connections:write` scope (`xapp-…`). It can't be created via API, so issue it in the UI.
- **Invite the bot to the channel** — For private channels or when auto-invite is blocked.

During interactive runs, the wizard asks for the following identifiers (not secrets). For headless runs (`--answers-file`),
provide them in advance under the same keys.

- **Meeting channel ID** (`channel_id`, `Cxxxxxxxx`) — The target for auto-inviting and wiring participant bots.
- **Your own Slack User ID** (`human_user_id`, `Uxxxxxxxx`) — Included in the allow-list.
- **Moderator Bot User ID** (`moderator_bot_user_id`, `Uxxxxxxxx`) — The bot of the base Hermes app.
  This value is required for the moderator to be included in `SLACK_ALLOWED_USERS` so that moderator→participant
  mention routing works (if missing, participants ignore moderator mentions).

> The wizard never prints bot/app tokens; they are stored only in each profile's `.env` with `0600` permissions.
> `--dry-run` only shows the planned actions without actually creating Slack apps or writing tokens.

## Slash command swap

A Slack workspace allows at most 50 slash commands per app. To make room, the extension removes 2 default commands
and adds the same number, **keeping the total count unchanged**.

| Feature | Default command removed | Command added |
| ------- | ----------------------- | ------------- |
| board   | `/footer`               | `/board`      |
| meeting | `/sethome`              | `/meeting`    |

Removed commands don't lose their functionality. You can still invoke them through Hermes's dispatcher (`/hermes <command>`)
(e.g., `/hermes footer`). The removed list is recorded as `slash_dropped` in the install state.

## `/meeting` Block Kit runtime (P3)

When you install the meeting feature, the `meeting_runtime` step idempotently patches the `/meeting` handler into the Hermes gateway's `slack.py`
and installs the overlay module (`slack_meeting_room.py`). A Block Kit control surface is layered on top of the text `/meeting` (P2).

- **`/meeting`** → ephemeral meeting room: header `Hermes Meeting Room`, `Start new meeting` and `Refresh` buttons,
  and meeting rows (title, status, attendees + action buttons).
- **New meeting modal** (6 fields): topic/goal / attendees (multi-select of configured participant personas, or text if none) /
  number of turns / progress mode (`mixed`, `sequential`, `parallel`, `directed`) / progress control (`auto`, `manual`) /
  voice mode (`voice-summary`, `text-only`, `voice-full`, `hybrid`).
- **Meeting actions**: `Start` / `Continue` (modal) / `Next: <profile>` (only in manual routing) / `End`.
  Each action injects a prompt into the meeting's **dedicated session** (`session_thread_id = meeting:<channel>:<id>`) —
  the moderator agent runs in a session **separate** from regular `@mention`/channel conversations.
  - `auto`: the moderator immediately calls the next single participant. `manual`: waits for the `Next: <profile>` button in the UI.
- **Session store**: `$HERMES_HOME/hermes-slack-ext/meeting_sessions.json` (meetings/current/`session_thread_id`).
  Participant persona display names are read as modal options from the `meeting_participants.json` sidecar
  (recorded by the wizard from the P2 profiles; excluding the base_app moderator).

> Note: among the default set of 4, "Developer" uses the `backend_engineer` preset, so its bot/meeting display name is **"Backend"**
> (routing, env, and prompts are all consistent based on the persona display name). To change the display name, edit the persona in profile custom
> mode.

## Diagnostics and rollback (doctor / uninstall)

### `hermes-ext doctor`

Diagnoses the install state (no token required).

```
hermes-ext doctor --hermes-root ~/.hermes/hermes-agent
```

Reported items: Hermes version, existence of `slack.py`, whether the board/meeting patches are applied, installed overlays,
backup availability, install record (features, dropped slash commands), and number of created apps. If patches exist but there's no install record
(e.g., a different machine or a manual patch), it warns and notes that uninstall will operate only based on backups/markers.

### `hermes-ext uninstall`

The inverse operation of install. **First review the plan with `--dry-run`.**

```
hermes-ext uninstall --dry-run                 # print rollback plan only (no changes)
hermes-ext uninstall --yes                     # roll back without confirmation
hermes-ext uninstall --yes --delete-apps       # also delete created participant apps
```

Rollback behavior: ① restore `slack.py` from backup (= unpatch) → ② delete overlay modules
(`slack_kanban_board.py`, `slack_meeting_room.py` + tests) → ③ clean up meeting artifacts (session store,
participant sidecar, base manifest, moderator skill, staging) → ④ (`--delete-apps`)
delete created apps via `apps.manifest.delete` → ⑤ guide the gateway restart.

- **Token rules**: The config token for app deletion is accepted only via the **environment variable `HSE_CONFIG_TOKEN`** or an interactive password
  prompt — tokens are never placed in CLI arguments or logs. If there's no token, app deletion is skipped and the
  `app_id` values to delete manually are shown.
- **Preservation**: Each profile's `.env` (which holds bot/app tokens) is preserved by default (so secrets aren't deleted by accident).
- **When backups are missing**: It only guides you instead of restoring automatically (no destructive actions such as force-removing markers).

### install ↔ uninstall symmetry

| Install                                          | Rollback                                                                |
| ------------------------------------------------ | ----------------------------------------------------------------------- |
| Patch `slack.py` after backup                    | Restore `slack.py` from backup (unpatch)                                |
| Copy overlay modules                             | Delete overlay modules                                                  |
| Create participant apps (`apps.manifest.create`) | (`--delete-apps`) `apps.manifest.delete`                                |
| Install meeting artifacts and skill              | Clean up meeting artifacts and skill                                    |
| Slash swap (base manifest)                       | Report `slash_dropped` (reverting the base manifest is guided manually) |

> Automatically reverting the slash swap in the base (moderator) app manifest requires a snapshot of the original manifest,
> which is out of scope for now. Since doctor reports `dropped`, revert it manually in the Slack App Manifest or
> regenerate and apply it with `hermes slack manifest`.

## Verification levels

- **L1 (code)** — `pytest` unit tests. Slack API and token prompts are all handled with mocks.
- **L2 (headless)** — Clone a real Hermes checkout and drive the wizard end to end with `--answers-file`
  (`tests/e2e/test_headless_meeting_setup.py`). The Slack API is mocked; no real tokens needed.
- **L3 (real Slack, tokens required)** — The checklist below. Only this level uses real tokens.

### L3 smoke checklist

1. Run the wizard to completion with a config token and participant tokens, all the way through real app creation, installation, and invitation.
2. Confirm `board patched ✓`, `meeting patched ✓`, and the install record via `hermes-ext doctor`.
3. Restart the gateway: `hermes gateway restart`.
4. **Block Kit**: In the meeting channel, `/meeting` → meeting room → submit the `Start new meeting` modal →
   the moderator presents a setup draft in the **dedicated session** (separate from regular `@mention`s).
5. `Start` → in auto mode the moderator calls the next single participant; in manual mode, route one turn with `Next: <profile>`.
6. Inject follow-up messages with `Continue`, and wrap up with a summary via `End`. Confirm that participant bots respond bot-to-bot based on mentions.
7. (Text fallback) Confirm that even without Block Kit, the text invocation `/meeting <topic>` drives the meeting via the moderator skill.
8. **Rollback round-trip**: Review the plan with `hermes-ext uninstall --dry-run` →
   `hermes-ext uninstall --yes --delete-apps` (env `HSE_CONFIG_TOKEN`) → confirm `✗` with `doctor` →
   after restarting the gateway, confirm that `/board` and `/meeting` have disappeared and the original state is restored.

## Roadmap

All stages P0–P4 are merged into master (board + deterministic meeting setup + meeting Block Kit runtime + rollback/diagnostics).
All that remains is **L3 real-world testing** (running the smoke checklist above with real Slack tokens).

## License

Internal tool. Requires workspace administrator approval before use.
