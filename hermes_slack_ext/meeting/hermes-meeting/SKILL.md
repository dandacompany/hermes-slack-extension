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

Use:

```text
회의 설정 초안
제목: ...
목표/산출물: ...
참여자: ...
턴수: ...
진행: ...
진행 제어: auto | manual
음성: ...
개입: ...
합의 품질: ...
종료 조건: ...

이 설정으로 시작할까요?
Slack Block Kit `/meeting` UI가 설치된 환경에서는 사용자가 UI의 `시작` 버튼으로 승인한다고 안내한다.
이후 사용자의 `이어쓰기`와 `종료`도 `/meeting` UI 액션으로 받으며, 일반 `@<moderator> ...` 멘션은 meeting 세션으로 간주하지 않는다.
```

Only start when the user clearly approves.
If a message arrives through the dedicated `/meeting` UI session after a setup draft, treat it as continuation of the pending meeting session. If the message is an approval such as `시작`, start the meeting from the existing state. Do not treat normal `@<moderator> ...` Slack mentions as meeting continuation when Block Kit meeting UI is installed.

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
- Use the visible profile name in routing text, such as `<PARTICIPANT_NAME> 1턴입니다.` The gateway may convert that line to the real Slack mention internally.
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
- Include: `병렬 응답: 서로를 멘션하지 말고, 끝에 handoff를 쓰지 말고, [PARALLEL-DONE]으로 끝내세요.`
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
- `voice-summary`: participant adds one final `음성 요약:` sentence.
- `voice-full`: participant writes 2-4 natural spoken Korean sentences.
- `hybrid`: moderator states which turns are spoken.

For any voice mode except `text-only`, wrap the exact speakable Korean in `[TTS]...[/TTS]`.
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
- `회의 종료`
