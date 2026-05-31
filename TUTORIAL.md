# Hermes Slack Extension — User Guide

`hermes-ext` is a deterministic install wizard that patches a self-hosted
**Hermes Agent 0.15.x** and adds two Slack Block Kit experiences:

- **`/board`** — a Kanban board you drive with buttons and natural language.
- **`/meeting`** — a multi-bot meeting room where a moderator and participant
  profiles run a structured, self-driving discussion in the channel.

It auto-generates the Slack app manifests, swaps two unused native slash commands
for `/board` and `/meeting`, and supports a clean uninstall.

This guide walks you from installation through everyday use.

---

## 1. Prerequisites

- A **self-hosted Hermes Agent 0.15.x** checkout (default `~/.hermes/hermes-agent`)
  running in **Socket Mode**, with its Python venv.
- A **Slack workspace** where you can install apps.
- A Slack **App Configuration Token** (`xoxe.xoxp-…`), used to create the
  participant apps and validate/generate manifests.
  Get it at <https://api.slack.com/apps> → _Your Apps_ → **App Configuration Tokens**.
- The base Hermes Slack app already installed (its bot token / app-level token),
  which becomes the meeting **moderator**.
- Python 3.10+ to run the wizard.

> The wizard never prints secrets. Tokens are read from prompts (hidden input) or
> the environment and written only to the relevant `.env` files at `0600`.

---

## 2. Installation

### Option A — one-line bootstrap (recommended)

```bash
curl -fsSL <raw-url>/scripts/install-remote.sh | bash
```

This creates an isolated venv, installs the package, links `hermes-ext` into
`~/.local/bin`, and runs the install wizard.

### Option B — manual

```bash
pip install hermes-slack-extension      # or: pip install -e .  from a checkout
hermes-ext install                      # run the wizard
```

Useful flags:

| Flag                                        | Purpose                                                     |
| ------------------------------------------- | ----------------------------------------------------------- |
| `--hermes-root PATH`                        | Hermes checkout to patch (default `~/.hermes/hermes-agent`) |
| `--dry-run`                                 | Show what would change without writing anything             |
| `--answers-file FILE` + `--non-interactive` | Headless install from a YAML answers file                   |
| `--state-dir PATH`                          | Where install state / backups / records live                |

### What the wizard does (10 steps)

1. **Detect** the Hermes checkout and version-gate it (0.15.x).
2. **Select features** — choose `board`, `meeting`, or both.
3. **Board** — back up and patch `slack.py`, copy the board overlay.
4. **Slash swap** — generate the base app manifest that replaces two unused
   native slashes with `/board` and `/meeting`.
5. **Meeting profiles** — pick the meeting participants (default 4: Moderator,
   Researcher, Backend, Designer), from presets or custom personas.
6. **Config token** — paste your App Configuration Token (hidden input).
7. **Slack apps** — create one Slack app per participant via
   `apps.manifest.create`, capture each bot/app-level token, run `auth.test`,
   and join the channel.
8. **Moderator app** — apply the moderator (base app) manifest.
9. **Wireup** — write each profile's channel prompt, bot-to-bot env
   (`SLACK_ALLOW_BOTS=mentions`, etc.), install the moderator skill, and write the
   mention map (profile name → bot user id) used for auto routing.
10. **Meeting runtime** — patch `slack.py` for `/meeting`, copy the meeting
    overlay, and write the participant sidecar.

The wizard is **resumable** — re-running continues from the last completed step.

### After install

Apply the generated manifests in the Slack app settings if the wizard could not
do it via the config token, invite every bot to the target channel, then restart
the gateway:

```bash
hermes gateway restart
```

---

## 3. Verify the install

```bash
hermes-ext doctor
```

Reports whether `slack.py` is **board patched** / **meeting patched**, which
overlays are present, whether a clean backup exists, and the install record. Use
it any time to confirm state before/after changes.

---

## 4. Using `/board` (Kanban)

In any channel where the bot is present:

```
/board
```

This posts a Block Kit board. You can:

- **Add / Move / Detail / Approve** tasks with the buttons.
- Use **natural language** with the bot — for example
  `add a "collect AI news" task`, `show the ready tasks as text`,
  `move t_abc123 to in-progress`, `summarize only tasks needing approval`.
  (Both English and Korean phrasings are recognized.)

---

## 5. Using `/meeting` (multi-bot meeting room)

### 5.1 Open the room

```
/meeting
```

An ephemeral **Meeting Room** launcher appears (visible only to you) with
**New meeting** and **Refresh**.

### 5.2 Create a meeting

Press **New meeting** and fill the modal:

- **Topic & goal**
- **Participants** (e.g. Researcher, Backend, Designer)
- **Turns** (total speaking turns, e.g. 4)
- **Mode** — `mixed` / `sequential` / `parallel` / `directed`
- **Routing** — `auto` (the moderator drives) or `manual` (you pick each speaker)
- **Voice** — `text-only` / `voice-summary` / `voice-full` / `hybrid`

Press **Create**. A persistent **Meeting Controls** card appears in the channel
with a **Start** button. Creating does _not_ start the meeting yet.

### 5.3 Run the meeting

1. **Start** → the moderator posts a short, clean **setup draft** (title, goal,
   participants, plan) and asks for approval. The card then shows **Approve /
   Continue / End**.
   _(The moderator runs on a reasoning model; a reply can take up to a minute.
   While it is thinking, the card shows a "responding…" state with no buttons, so
   you never press a button before the answer is visible.)_
2. **Approve** → the meeting begins.
   - In **auto** routing, the moderator addresses the next speaker (e.g.
     `@Researcher`), that participant bot replies and hands back to the
     moderator, who then routes the next speaker — the meeting **self-drives**
     turn by turn to the final synthesis.
   - In **manual** routing, use the **Next: \<name\>** buttons on the card to pick
     each speaker.
3. **Continue** → add your own message / intervention mid-meeting.
4. **End** → the moderator summarizes decisions, open questions, and next actions.

The whole conversation happens in the **channel body** (not a thread), and the
**Meeting Controls** card follows along below the latest reply. Internal
scaffolding (state blocks, hand-off labels) is hidden — you see a natural
discussion. Meeting messages are rendered in the language of your topic (a Korean
topic yields a Korean meeting).

> A full auto meeting of several turns takes a few minutes because each turn is a
> full model response. If auto routing stalls, use **Next** to nudge it, or
> **End** to wrap up.

---

## 6. Uninstall

```bash
hermes-ext uninstall            # interactive; shows a plan first
hermes-ext uninstall --dry-run  # preview only
hermes-ext uninstall --yes --delete-apps
```

Uninstall restores `slack.py` from the clean backup (unpatch), removes the
overlays, cleans up meeting artifacts (sidecars, sessions store), and — with
`--delete-apps` — deletes the participant Slack apps it created. Restart the
gateway afterward.

---

## 7. Troubleshooting

| Symptom                                         | Cause / fix                                                                                                                                                                            |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A participant is never called in auto routing   | Every bot needs the patched gateway code **and** the `meeting_mentions.json` mention map in its `HERMES_HOME`. If profiles run in separate containers, deploy the patch + map to each. |
| Buttons appear before the reply                 | Expected only briefly; the card hides buttons (“responding…”) until the model replies, then re-posts them below the answer.                                                            |
| The moderator keeps using an old message format | The agent **session is persisted** and resumes across restarts. Reset it (`/new`, or clear `HERMES_HOME/sessions/sessions.json`) so the current prompts/skill take effect.             |
| `/board` or `/meeting` not delivered            | The command must be declared in the app manifest _and_ Socket Mode connected. Re-check the manifest and `hermes-ext doctor`.                                                           |
| Bots don't reply to each other                  | Each profile's `.env` needs `SLACK_ALLOW_BOTS=mentions` and the bot must be in the channel.                                                                                            |

---

## 8. Verification levels (for contributors)

- **L1** — unit tests: `pytest tests/ hermes_slack_ext`
- **L2** — headless install against a fixture Hermes checkout.
- **L3** — live install against a real Slack workspace; verified via the Slack
  Web API (`conversations.history`), not just gateway logs.
