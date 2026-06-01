# Hermes Slack Extension

한국어 문서: [README.ko.md](README.ko.md)

Turn your self-hosted **Hermes Agent** into a richer Slack workspace with two
Block Kit experiences:

- **`/board`** — a Kanban board you drive with buttons and natural language.
- **`/meeting`** — a multi-bot meeting room where a moderator and participant
  personas run a structured, self-driving discussion right in the channel.

`hermes-ext` is a **deterministic install wizard**: it patches Hermes
`gateway/platforms/slack.py`, auto-generates the Slack app manifests, creates the
participant apps, and wires everything up — the same inputs always produce the
same result. It also uninstalls cleanly.

> Works with **Hermes Agent 0.15.x** (supported range 0.12.0–0.15.1) running in
> Socket Mode.

---

## What you get

| Feature               | What it adds                                                                                                                                                                            |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`/board`**          | A Kanban Block Kit board — Add / Move / Detail / Approve tasks, plus natural-language commands (English & Korean).                                                                      |
| **`/meeting`**        | A meeting room: pick participants and a format, then the bots take turns automatically (auto routing) and post a clean, natural discussion in the channel, with an inline control card. |
| **Slash swap**        | Frees room under Slack's 50-command limit by retiring two unused defaults and adding `/board` + `/meeting` (the retired ones still work via `/hermes <command>`).                       |
| **Manifest auto-gen** | Builds the Slack manifests from your installed Hermes's command registry and enables Socket Mode + interactivity automatically.                                                         |

---

## Prerequisites

- A self-hosted **Hermes Agent 0.15.x** checkout (default `~/.hermes/hermes-agent`)
  running in **Socket Mode**, with its Python venv.
- A **Slack workspace** where you can install apps, and the base Hermes Slack app
  already installed (it becomes the meeting **moderator**).
- A Slack **App Configuration Token** (`xoxe.xoxp-…`) — used to create the
  participant apps and apply manifests. Get it at
  <https://api.slack.com/apps> → **App Configuration Tokens**.
- Python 3.10+ to run the wizard.

> The wizard never prints secrets. Tokens are read from hidden prompts (or the
> environment) and written only to the relevant `.env` files at `0600`.

---

## Installation

> The remote commands assume the repo is hosted at
> `github.com/dandacompany/hermes-slack-extension` (the default in
> `scripts/install-remote.sh`). Until it is published there, use **Option C
> (local checkout)**. Override the source any time with `HSE_REPO` / `HSE_REF`.

**Option A — one-line bootstrap** (once published)

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-extension/main/scripts/install-remote.sh | bash
```

Creates an isolated venv under `~/.hermes/hermes-slack-ext/venv`, installs the
package from GitHub, links `hermes-ext` into `~/.local/bin`, and runs the wizard.

**Option B — from GitHub**

```bash
pip install "git+https://github.com/dandacompany/hermes-slack-extension@main"
hermes-ext install
```

**Option C — from a local checkout** (works today)

```bash
git clone https://github.com/dandacompany/hermes-slack-extension
cd hermes-slack-extension
pip install -e .
hermes-ext install
```

### Wizard flags

| Flag                                        | Purpose                                                     |
| ------------------------------------------- | ----------------------------------------------------------- |
| `--hermes-root PATH`                        | Hermes checkout to patch (default `~/.hermes/hermes-agent`) |
| `--dry-run`                                 | Show planned changes without writing anything               |
| `--answers-file FILE` + `--non-interactive` | Headless install from a YAML answers file                   |
| `--state-dir PATH`                          | Where install state / backups / records live                |

### What the wizard does

The wizard detects and version-gates Hermes, lets you select features
(`board` / `meeting`), then runs the relevant steps. For `/meeting` it:

1. **Configures meeting profiles** — accept the default 4 (Moderator, Researcher,
   Developer→**Backend**, Designer) or pick presets / custom personas
   (no LLM, fully deterministic). The moderator is your **existing base Hermes
   app**; the participants are newly created minimal-manifest apps.
2. **Captures the App Configuration Token** (hidden input) — one token creates
   every app in the workspace.
3. **Creates participant apps** via `apps.manifest.create`, captures each Bot
   Token + App-Level Token, runs `auth.test`, and joins the channel.
4. **Applies the moderator manifest** (the slash swap), or points you to the
   manifest file for manual application.
5. **Wires bot-to-bot** — writes each profile's channel prompt and `.env`
   (`SLACK_ALLOW_BOTS=mentions`, allow-list of all bots), installs the moderator
   skill, and writes the **mention map** (profile name → bot user id) used for
   auto routing.

The wizard is **resumable** — re-running continues from the last completed step.

### Identifiers the wizard asks for

These are not secrets (provide them under the same keys in headless runs):

- **Meeting channel ID** (`channel_id`, `Cxxxxxxxx`)
- **Your Slack User ID** (`human_user_id`, `Uxxxxxxxx`)
- **Moderator Bot User ID** (`moderator_bot_user_id`, `Uxxxxxxxx`) — required so
  the moderator is in the allow-list and routing works.

### Manual Slack steps (UI/OAuth only)

The wizard guides you through what Slack can't automate:

- Issue an **App Configuration Token** (api.slack.com/apps).
- **Install each participant app** (Install to Workspace) → issues a Bot Token.
- Issue an **App-Level Token** with the `connections:write` scope (`xapp-…`).
- **Invite each bot** to the channel (for private channels / blocked auto-invite).

### After install

```bash
hermes gateway restart
```

---

## Verify

```bash
hermes-ext doctor
```

Reports whether `slack.py` is **board patched** / **meeting patched**, which
overlays are present, whether a clean backup exists, and the install record.

---

## Using `/board`

In a channel where the bot is present:

```
/board
```

- **Add / Move / Detail / Approve** tasks with the buttons.
- Or use natural language with the bot — e.g. `add a "collect AI news" task`,
  `show the ready tasks as text`, `move t_abc123 to in-progress`,
  `summarize only tasks needing approval` (English and Korean both work).

---

## Using `/meeting`

### 1. Open the room

```
/meeting
```

An ephemeral **Meeting Room** (visible only to you) appears with **New meeting**
and **Refresh**.

### 2. Create a meeting

Press **New meeting** and fill the modal: topic & goal, participants, turns,
mode (`mixed` / `sequential` / `parallel` / `directed`), routing (`auto` /
`manual`), voice (`text-only` / `voice-summary` / `voice-full` / `hybrid`).

Press **Create** — a **Meeting Controls** card appears in the channel with a
**Start** button. Creating does _not_ start the meeting yet.

### 3. Run it

1. **Start** → the moderator posts a short, clean **setup draft** and asks for
   approval. The card then shows **Approve / Continue / End**.
2. **Approve** → the meeting begins.
   - **auto** routing: the moderator addresses the next speaker (e.g.
     `@Researcher`), that bot replies and hands back, and the moderator routes the
     next one — the meeting **self-drives** to a final synthesis.
   - **manual** routing: use the **Next: \<name\>** buttons to pick each speaker.
3. **Continue** → add your own message mid-meeting.
4. **End** → the moderator summarizes decisions, open questions, and next actions.

The whole discussion happens in the **channel body**, and the Meeting Controls
card follows along below the latest reply. Internal scaffolding (state blocks,
hand-off labels) is hidden, so you read a natural conversation; messages are
rendered in your topic's language.

> The moderator runs on a reasoning model, so each turn can take up to a minute.
> While it thinks, the card shows a "responding…" state with **no buttons** — so
> you never press the next button before the answer is visible. A full auto
> meeting of several turns takes a few minutes; if it stalls, use **Next** to
> nudge it or **End** to wrap up.

### Meeting options

The **New meeting** modal exposes the options below. They are passed to the
moderator as a prompt contract — the moderator (an LLM) interprets and follows
them; the mechanical parts (`@Name` → real mention, threading) are enforced by
the gateway.

**Mode** — how turns are distributed:

| Value               | Behavior                                                                                                                                                           | Use when                                                            |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| `mixed` _(default)_ | The moderator declares a phase plan and mixes modes per phase (e.g. `framing: moderator`, `divergence: parallel`, `critique: sequential`, `synthesis: moderator`). | The most meeting-like flow: diverge → critique → synthesize.        |
| `sequential`        | One speaker at a time; each reply hands back before the next is called, so participants build on each other.                                                       | Deep, ordered discussion (slower: ~1 min × participants per round). |
| `parallel`          | Several participants are called at once and reply independently (no cross-mentions); the moderator summarizes after all respond.                                   | Fast divergence / brainstorming; independent perspectives.          |
| `directed`          | A single targeted question to one profile, then back to the previous flow.                                                                                         | Asking just one expert.                                             |

**Routing** — who picks the next speaker:

| Value              | Behavior                                                                                         | Use when                                    |
| ------------------ | ------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| `auto` _(default)_ | The moderator calls the next speaker automatically (`@Name`); the bots self-drive — no clicking. | Hands-off, autonomous meetings.             |
| `manual`           | No auto-routing; you pick each speaker with the **Next: \<name\>** button on the card.           | Maximum control / demos (a click per turn). |

**Voice** — text-to-speech output:

| Value                       | Behavior                                                                          |
| --------------------------- | --------------------------------------------------------------------------------- |
| `voice-summary` _(default)_ | Each reply ends with one "voice summary" sentence, wrapped in `[TTS]` for speech. |
| `text-only`                 | No voice — text only.                                                             |
| `voice-full`                | The whole reply is 2–4 natural spoken sentences, wrapped in `[TTS]`.              |
| `hybrid`                    | The moderator decides which turns are spoken.                                     |

Only the `[TTS]…[/TTS]` portion is spoken; Slack uploads default to MP3.

**Turns** _(default 4)_ — total speaking turns. Only substantive participant
replies and the final moderator synthesis count; routing, metadata, retries, and
user interventions do not.

**Recommended combinations**

- General meeting: `mixed` + `auto` _(default)_ — natural multi-phase discussion.
- Quick idea collection: `parallel` + `auto`.
- Precise control / demo: `sequential` + `manual`.
- Single-expert question: `directed`.

> Each turn takes ~1 minute (the reasoning model), so `sequential` × many turns ×
> many participants can run for several minutes. For speed, use `parallel` or
> fewer turns.

---

## Slash command swap

Slack allows at most 50 slash commands per app. To make room, the extension
retires two unused defaults and adds the same number — total count unchanged:

| Feature | Retired    | Added      |
| ------- | ---------- | ---------- |
| board   | `/footer`  | `/board`   |
| meeting | `/sethome` | `/meeting` |

Retired commands keep working through Hermes's dispatcher: `/hermes footer`,
`/hermes sethome`. The retired list is recorded as `slash_dropped`.

---

## Diagnostics & uninstall

```bash
hermes-ext uninstall --dry-run                 # print the rollback plan only
hermes-ext uninstall --yes                     # roll back without confirmation
hermes-ext uninstall --yes --delete-apps       # also delete the created participant apps
```

Uninstall is the inverse of install: ① restore `slack.py` from the clean backup
(unpatch) → ② remove the overlay modules → ③ clean up meeting artifacts (session
store, mention map, participant sidecar, base manifest, moderator skill, staging)
→ ④ (with `--delete-apps`) delete the created apps via `apps.manifest.delete`.

- **Token rule**: app deletion reads the config token only from the
  `HSE_CONFIG_TOKEN` env var or an interactive password prompt — never from CLI
  args or logs. Without a token, deletion is skipped and the `app_id`s to remove
  are printed.
- Each profile's `.env` (bot/app tokens) is **preserved** by default.
- Reverting the base app's slash swap is guided manually (it needs the original
  manifest snapshot); `doctor` reports the dropped commands.

Restart the gateway after uninstalling.

---

## Troubleshooting

| Symptom                                         | Cause / fix                                                                                                                                                                            |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A participant is never called in auto routing   | Every bot needs the patched gateway code **and** the `meeting_mentions.json` mention map in its `HERMES_HOME`. If profiles run in separate containers, deploy the patch + map to each. |
| The moderator keeps using an old message format | The agent **session is persisted** and resumes across restarts. Reset it (`/new`, or clear `HERMES_HOME/sessions/sessions.json`) so the current prompts/skill take effect.             |
| `/board` or `/meeting` isn't delivered          | The command must be declared in the manifest **and** Socket Mode connected. Re-check the manifest and `hermes-ext doctor`.                                                             |
| Bots don't reply to each other                  | Each profile's `.env` needs `SLACK_ALLOW_BOTS=mentions` and the bot must be in the channel.                                                                                            |

---

## For contributors

Verification runs at three levels:

- **L1 (unit)** — `pytest tests/ hermes_slack_ext` (Slack API and prompts mocked).
- **L2 (headless)** — drive the wizard end to end against a fixture Hermes
  checkout with `--answers-file`.
- **L3 (live)** — install against a real Slack workspace; behavior is verified
  via the Slack Web API (`conversations.history`), not just gateway logs.

---

## License

Internal tool — check with your workspace administrator before use.
Copyright © 2026 Dante Labs.

---

<div align="center">

**YouTube** [@dante-labs](https://youtube.com/@dante-labs) · **Email** dante@dante-labs.com · [☕ Buy Me a Coffee](https://buymeacoffee.com/dante.labs)

</div>
