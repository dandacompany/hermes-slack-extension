---
name: hermes-meeting
description: Socratic moderator workflow for Hermes multi-profile Slack meetings. Use when /meeting is invoked or a user wants a structured multi-agent meeting.
---

# Hermes Meeting Moderator

The profile that receives `/meeting` is the meeting entrypoint. By default, the selected moderator profile moderates the meeting.

Follow the ground rules in `references/meeting-ground-rules.md` when this skill is installed as part of `hermes-slack-meeting-room`.

## Setup First

Do not start by mentioning participants. First confirm:

- Meeting title
- Goal and expected output
- Participants
- Total speaking turns
- Mode: sequential, parallel, directed, or mixed
- Voice mode: text-only, voice-summary, voice-full, or hybrid
- Routing control: auto or manual
- User intervention rule
- Anti-convergence rule
- Finish condition

Render all user-facing meeting text — the setup draft labels below, routing
phrases, summaries, and the closing line — in the language of the meeting topic
and participants (for example, Korean for a Korean-language meeting). The labels
below are an English template; translate them into the meeting language.

Use:

```text
Meeting setup draft
Title: ...
Goal / output: ...
Participants: ...
Turns: ...
Mode: ...
Routing: auto | manual
Voice: ...
Intervention: ...
Consensus quality: ...
Finish condition: ...

Shall we start with this setup?
```

When the Slack Block Kit `/meeting` UI is installed, the user approves via the
channel _Meeting Controls_ card buttons (Start, then Approve), not by typing.
Continue/End and next-speaker selection also arrive through those buttons. Normal
`@<moderator> ...` mentions are not treated as a meeting session.

Only start when the user clearly approves.
If a message arrives through the dedicated `/meeting` UI session after a setup draft, treat it as continuation of the pending meeting session. If the message is an approval (such as the one sent by the Approve button), start the meeting from the existing state and do not reprint the setup draft. Do not treat normal `@<moderator> ...` Slack mentions as meeting continuation when Block Kit meeting UI is installed.

If routing control is `auto`, immediately route one next speaker. If routing control is `manual`, do not route the next participant automatically; wait until the user selects the next speaker in the `/meeting` UI.

## State

Maintain a compact state block on every routing, pause, resume, synthesis, or decision message:

```text
[MEETING]
id: <short-id>
status: setup | active | paused | waiting | ended
mode: sequential | parallel | directed | mixed
phase: framing | divergence | critique | synthesis | decision
turns: <counted>/<total>
current_speaker: <profile-or-none>
pending: <profiles-or-none>
completed: <profiles-or-none>
next: <profile-or-action>
last_event: <brief>
[/MEETING]
```

Only substantive participant replies and final moderator synthesis count as turns. Routing, metadata, retries, and user clarification do not count as turns.

## Routing

Only the moderator assigns speaking turns. If the user speaks, pause routing and classify the intervention before mentioning another participant.

Slack routing rule:

- Every routed turn must target only one selected profile.
- Use the visible profile name in routing text, such as `<PARTICIPANT_NAME>, your turn (1 turn).` (render the phrase in the meeting language). The gateway may convert that line to the real Slack mention internally.
- Do not ask the user for Slack user IDs and do not print mention maps or ID examples in warnings, explanations, code blocks, or checklists.
- Every routed turn must include enough context for that participant to answer from the current meeting state: the `[MEETING]` block, the relevant prior decisions or disagreement, and the bounded question for that profile.
- In sequential handoff, participants use the visible moderator mention form `handoff: @<MODERATOR_NAME>`, replacing `<MODERATOR_NAME>` with the moderator shown in the meeting state or routing prompt.

Sequential mode:

- Mention exactly one participant.
- Participant substantive replies count as turns.
- Moderator routing messages do not count as turns.
- Participants hand back with `handoff: @<MODERATOR_NAME>`.
- Do not route to the next participant until the expected participant answers, the user intervenes, or the timeout policy is triggered.

Parallel mode:

- Mention multiple participants once.
- Include this instruction (phrased in the meeting language): for parallel replies, do not mention each other, do not add a handoff at the end, and finish with `[PARALLEL-DONE]`.
- Summarize only after all expected participants respond or the user asks to summarize.
- If a participant is missing, mark them as missing. Do not invent their position.

Directed mode:

- Use for a single targeted question to one profile.
- Return to the previous flow after that turn.

Mixed mode:

- Declare a short phase plan before starting mixed routing.
- Example: `framing: moderator`, `divergence: parallel`, `critique: sequential`, `synthesis: moderator`.

## Off-Protocol Handling

- Duplicate answer: count only the first substantive answer unless a revision was requested.
- Late answer: add a one-line correction only if it changes the current synthesis; do not reopen the meeting automatically.
- Cross-mention: remind the participant that only the moderator routes turns.
- Missing participant: retry once with a shorter prompt, then continue and record `missing: <profile>`.

## Anti-Convergence

At halfway and before the final decision, ask for one of:

- Counterargument
- Failure scenario
- Missing stakeholder
- Weak assumption
- Metric or verification signal

If all participants converge too quickly, assign contrasting frames to the next turns.

## User Intervention

If the user speaks mid-meeting, first classify the message:

- `pause`: stop routing and wait.
- `stop`: end the meeting with current state.
- `revise`: change title, goal, participants, mode, voice mode, turn count, or constraints.
- `answer`: user provides missing information.
- `comment`: user adds context without changing the plan.
- `direct`: user asks a specific participant or the moderator a targeted question.

Then:

1. Pause routing.
2. Summarize the changed constraint in one sentence.
3. Update the state block.
4. Revise the next speaker or mode.
5. Continue only after the next action is clear.

## Voice Modes

- `text-only`: no voice-specific formatting.
- `voice-summary`: participant adds one final "voice summary:" sentence (label rendered in the meeting language).
- `voice-full`: participant writes 2-4 natural spoken sentences in the meeting language.
- `hybrid`: moderator states which turns are spoken.

For any voice mode except `text-only`, wrap the exact speakable text (in the meeting language) in `[TTS]...[/TTS]`.
Use `[TTS]` for only the summary sentence in `voice-summary`, and for only the spoken answer in `voice-full`.
Keep routing state, Slack mentions, handoff markers, and control metadata outside `[TTS]`.
For Slack file uploads, prefer MP3 output by default. Do not configure command TTS as `voice_compatible: true` unless the target platform explicitly requires Opus voice bubbles, because that setting can convert MP3 into OGG.

TTS must speak only meeting content. Do not speak:

```text
[MEETING]
[/MEETING]
round:
speaker_done:
next:
handoff:
participant mentions
[PARALLEL-DONE]
```

If precise spoken content matters, wrap only that content:

```text
[TTS]
...
[/TTS]
```

## Ending

At the final turn, mention no participant. End with:

- Decision or synthesis
- Open questions
- Next actions
- A closing line such as "Meeting closed" (rendered in the meeting language)
