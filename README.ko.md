# Hermes Slack Extension

English README: [README.md](README.md)

자체 호스팅 중인 **Hermes Agent**를 두 가지 Block Kit 경험으로 더 풍부한 Slack
워크스페이스로 만들어 줍니다.

- **`/board`** — 버튼과 자연어로 다루는 칸반 보드.
- **`/meeting`** — 모더레이터와 참가자 페르소나들이 채널 안에서 구조화된 회의를
  스스로 진행하는 멀티봇 회의실.

`hermes-ext`는 **결정론적 설치 위저드**입니다. Hermes의
`gateway/platforms/slack.py`를 패치하고, Slack 앱 매니페스트를 자동 생성하며,
참가자 앱을 만들고 전체 배선까지 해줍니다 — 같은 입력은 항상 같은 결과를 냅니다.
깔끔한 제거(uninstall)도 지원합니다.

> Socket Mode로 동작하는 **Hermes Agent 0.15.x** (지원 범위 0.12.0–0.15.1)에서
> 작동합니다.

---

## 무엇을 얻나요

| 기능                     | 추가되는 것                                                                                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`/board`**             | 칸반 Block Kit 보드 — 추가 / 이동 / 상세 / 승인, 그리고 자연어 명령(한국어·영어).                                                                           |
| **`/meeting`**           | 회의실: 참가자와 진행 방식을 고르면 봇들이 자동으로 턴을 주고받으며(auto 라우팅) 채널에 깔끔하고 자연스러운 토론을 남기고, 인라인 컨트롤 카드를 제공합니다. |
| **슬래시 스왑**          | Slack의 50개 슬래시 제한 안에서 안 쓰는 기본 명령 2개를 빼고 `/board`·`/meeting`을 추가합니다(뺀 명령은 `/hermes <command>`로 계속 사용 가능).              |
| **매니페스트 자동 생성** | 설치된 Hermes의 명령 레지스트리에서 매니페스트를 만들고 Socket Mode·인터랙티비티를 자동으로 켭니다.                                                         |

---

## 사전 준비

- Socket Mode로 실행 중인 자체 호스팅 **Hermes Agent 0.15.x** 체크아웃
  (기본 `~/.hermes/hermes-agent`)과 그 Python venv.
- 앱을 설치할 수 있는 **Slack 워크스페이스**, 그리고 이미 설치된 기본 Hermes Slack
  앱(이 앱이 회의 **모더레이터**가 됩니다).
- Slack **App Configuration Token** (`xoxe.xoxp-…`) — 참가자 앱 생성과 매니페스트
  적용에 사용합니다. <https://api.slack.com/apps> → **App Configuration Tokens**.
- 위저드 실행용 Python 3.10+.

> 위저드는 시크릿을 절대 출력하지 않습니다. 토큰은 숨김 입력(또는 환경변수)으로
> 받아 각 `.env` 파일에 `0600` 권한으로만 기록합니다.

---

## 설치

> 원격 명령은 레포가 `github.com/dandacompany/hermes-slack-extension`에 호스팅돼
> 있다고 가정합니다(`scripts/install-remote.sh`의 기본값). 아직 거기에 게시되지
> 않았다면 **옵션 C(로컬 체크아웃)**를 사용하세요. `HSE_REPO` / `HSE_REF`로 소스를
> 언제든 오버라이드할 수 있습니다.

**옵션 A — 한 줄 부트스트랩** (게시 후)

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-extension/main/scripts/install-remote.sh | bash
```

`~/.hermes/hermes-slack-ext/venv`에 격리된 venv를 만들고, GitHub에서 패키지를
설치하고, `hermes-ext`를 `~/.local/bin`에 링크한 뒤 위저드를 실행합니다.

**옵션 B — GitHub에서 설치**

```bash
pip install "git+https://github.com/dandacompany/hermes-slack-extension@main"
hermes-ext install
```

**옵션 C — 로컬 체크아웃에서 설치** (지금 바로 가능)

```bash
git clone https://github.com/dandacompany/hermes-slack-extension
cd hermes-slack-extension
pip install -e .
hermes-ext install
```

### 위저드 플래그

| 플래그                                      | 용도                                                  |
| ------------------------------------------- | ----------------------------------------------------- |
| `--hermes-root PATH`                        | 패치할 Hermes 체크아웃(기본 `~/.hermes/hermes-agent`) |
| `--dry-run`                                 | 아무것도 쓰지 않고 변경 예정만 표시                   |
| `--answers-file FILE` + `--non-interactive` | YAML 답변 파일로 헤드리스 설치                        |
| `--state-dir PATH`                          | 설치 상태 / 백업 / 기록 위치                          |

### 위저드가 하는 일

위저드는 Hermes를 탐지·버전 게이트한 뒤, 기능(`board` / `meeting`)을 선택하게
하고 해당 단계를 실행합니다. `/meeting`의 경우:

1. **회의 프로필 구성** — 기본 4명(Moderator, Researcher, Developer→**Backend**,
   Designer)을 그대로 쓰거나 프리셋/커스텀 페르소나를 고릅니다(LLM 없이 완전
   결정론적). 모더레이터는 **기존 기본 Hermes 앱**, 참가자는 새로 만든 최소
   매니페스트 앱입니다.
2. **App Configuration Token 입력**(숨김) — 토큰 하나로 워크스페이스의 모든 앱을
   생성합니다.
3. **참가자 앱 생성** — `apps.manifest.create`로 앱을 만들고, 각 Bot Token +
   App-Level Token을 캡처하고, `auth.test`를 실행하고, 채널에 초대합니다.
4. **모더레이터 매니페스트 적용**(슬래시 스왑), 또는 수동 적용을 위해 매니페스트
   파일 경로를 안내합니다.
5. **봇 간 배선** — 각 프로필의 채널 프롬프트와 `.env`(`SLACK_ALLOW_BOTS=mentions`,
   전체 봇 allow-list)를 쓰고, 모더레이터 스킬을 설치하며, 자동 라우팅에 쓰이는
   **멘션 맵**(프로필 이름 → 봇 user id)을 기록합니다.
6. **TTS 구성** _(선택, 기본 꺼짐 → text-only)_ — 켜면 프로바이더(`edge` /
   `openai` / `gemini` / `elevenlabs` / …)를 고르고, 위저드가 각 프로필에 보이스를
   **라운드로빈**으로 배정합니다(프로필 수가 프로바이더 보이스 수보다 많으면 재사용).
   프로바이더 키 저장, SDK 설치, 프로필별 `tts` 설정 블록 스테이징까지 처리합니다.
   [Voice](#회의-옵션) 참고.

위저드는 **재개 가능**합니다 — 다시 실행하면 마지막으로 완료한 단계부터 이어집니다.

### 위저드가 묻는 식별자

시크릿이 아닙니다(헤드리스 실행 시 같은 키로 미리 제공):

- **회의 채널 ID** (`channel_id`, `Cxxxxxxxx`)
- **본인 Slack User ID** (`human_user_id`, `Uxxxxxxxx`)
- **모더레이터 Bot User ID** (`moderator_bot_user_id`, `Uxxxxxxxx`) — 모더레이터가
  allow-list에 포함돼 라우팅이 동작하려면 필요합니다.

### 직접 해야 하는 Slack 단계 (UI/OAuth 한정)

Slack이 자동화할 수 없는 부분은 위저드가 안내합니다.

- **App Configuration Token 발급** (api.slack.com/apps).
- **각 참가자 앱 설치**(Install to Workspace) → Bot Token 발급.
- `connections:write` 스코프의 **App-Level Token**(`xapp-…`) 발급.
- (비공개 채널/자동 초대 차단 시) **각 봇을 채널에 초대**.

### 설치 후

```bash
hermes gateway restart
```

---

## 검증

```bash
hermes-ext doctor
```

`slack.py`의 **board patched** / **meeting patched** 여부, 설치된 오버레이, 클린
백업 존재 여부, 설치 기록을 보고합니다.

---

## `/board` 사용

봇이 들어와 있는 채널에서:

```
/board
```

- 버튼으로 **추가 / 이동 / 상세 / 승인**.
- 또는 봇에게 자연어로 — 예: `"AI 뉴스 수집" 태스크 추가`,
  `ready 태스크 텍스트로 보여줘`, `t_abc123 진행중으로 이동`,
  `승인 필요한 것만 요약` (한국어·영어 모두 인식).

---

## `/meeting` 사용

### 1. 룸 열기

```
/meeting
```

본인에게만 보이는 ephemeral **Meeting Room**이 **New meeting**·**Refresh** 버튼과
함께 나타납니다.

### 2. 회의 생성

**New meeting**을 눌러 모달을 채웁니다: 주제·목표, 참석자, 턴 수, 모드(`mixed` /
`sequential` / `parallel` / `directed`), 라우팅(`auto` / `manual`),
음성(`text-only` / `voice-summary` / `voice-full` / `hybrid`).

**Create**를 누르면 채널에 **Start** 버튼이 있는 **Meeting Controls** 카드가
나타납니다. 생성만으로는 아직 회의가 시작되지 않습니다.

### 3. 진행

1. **Start** → 모더레이터가 짧고 깔끔한 **설정 초안**을 올리고 승인을 요청합니다.
   카드는 이제 **Approve / Continue / End**를 보여줍니다.
2. **Approve** → 회의 시작.
   - **auto** 라우팅: 모더레이터가 다음 발언자를 호명(예: `@Researcher`)하면 그
     봇이 답하고 다시 모더레이터에게 넘기며, 모더레이터가 다음 발언자를 호명 — 회의가
     최종 종합까지 **스스로 진행**됩니다.
   - **manual** 라우팅: 카드의 **Next: \<이름\>** 버튼으로 발언자를 직접 고릅니다.
3. **Continue** → 회의 중간에 직접 메시지를 추가.
4. **End** → 모더레이터가 결정·미해결 질문·다음 액션을 요약.

전체 토론은 **채널 본문**에서 이뤄지고, Meeting Controls 카드는 최신 응답 아래로
따라옵니다. 내부 스캐폴딩(상태 블록, 핸드오프 라벨)은 숨겨져 자연스러운 대화로
보이며, 메시지는 주제의 언어로 렌더링됩니다.

> 모더레이터는 추론 모델로 동작하므로 한 턴에 최대 1분 정도 걸릴 수 있습니다. 모델이
> 생각하는 동안 카드는 **버튼 없이** "responding…" 상태를 보여줘, 답이 보이기 전에
> 다음 버튼을 누르는 일이 없게 합니다. 여러 턴의 auto 회의는 몇 분 걸리며, 멈추면
> **Next**로 진행을 유도하거나 **End**로 마무리하세요.

### 회의 옵션

**New meeting** 모달의 옵션들입니다. 이 값들은 프롬프트 계약으로 모더레이터에게
전달되며, 모더레이터(LLM)가 해석·진행합니다. 기계적인 부분(`@이름` → 실제 멘션,
스레드 처리)은 게이트웨이가 보장합니다.

**Mode (진행 모드)** — 발언을 _어떻게_ 배분하나:

| 값               | 동작                                                                                                                                                      | 언제                                          |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| `mixed` _(기본)_ | 모더레이터가 단계 계획을 선언하고 단계별로 모드를 섞음(예: `framing: moderator`, `divergence: parallel`, `critique: sequential`, `synthesis: moderator`). | 가장 회의다운 흐름: 발산 → 비판 → 종합.       |
| `sequential`     | 한 번에 1명씩, 각 답변이 다음 호출 전에 모더레이터로 반환 → 서로의 발언 위에 쌓임.                                                                        | 깊고 정돈된 토론(느림: 라운드당 ~1분 × 인원). |
| `parallel`       | 여러 명을 한 번에 호출 → 각자 독립적으로(서로 멘션 없이) 답변 → 전원 답하면 모더레이터가 종합.                                                            | 빠른 발산/브레인스토밍, 독립 관점 수집.       |
| `directed`       | 특정 1명에게 단발 질문 후 원래 흐름으로 복귀.                                                                                                             | 한 명의 전문가에게만 질의.                    |

**Routing (진행 제어)** — 다음 발언자를 _누가_ 정하나:

| 값              | 동작                                                                             | 언제                           |
| --------------- | -------------------------------------------------------------------------------- | ------------------------------ |
| `auto` _(기본)_ | 모더레이터가 다음 발언자(`@이름`)를 자동 호출 → 봇들이 스스로 진행(클릭 불필요). | 손 안 대고 자율 진행.          |
| `manual`        | 자동 진행 없음. 카드의 **Next: \<이름\>** 버튼으로 매 턴 직접 발언자 지정.       | 최대 통제 / 시연(턴마다 클릭). |

**Voice (음성)** — TTS 출력:

| 값                   | 동작                                                                         |
| -------------------- | ---------------------------------------------------------------------------- |
| `text-only` _(기본)_ | 음성 없음 — 텍스트만.                                                        |
| `voice-summary`      | 각 답변이 자연스러운 결론 한 문장으로 끝나며 그 문장이 음성화(`[TTS]` 감쌈). |
| `voice-full`         | 답변 전체를 자연스러운 2–4문장 구어체로 `[TTS]` 감싸 음성화.                 |
| `hybrid`             | 모더레이터가 어떤 턴을 음성으로 할지 결정.                                   |

음성 동작: 모든 음성 모드에서 각 봇은 낭독할 텍스트를 `[TTS]…[/TTS]`로 감쌉니다.
게이트웨이는 **그 부분만** 해당 봇의 **고유 보이스**로 합성해 회의 스레드에 MP3로
업로드하고 마커는 제거합니다(문장은 텍스트로도 남음). 멘션·제어 마커는 낭독되지
않습니다. 프로필별 보이스는 위저드의 **TTS 단계**에서 배정되며, 이 단계를 건너뛰면
음성 모드로 설정해도 텍스트만 출력됩니다.

> **edge-tts 참고:** 무료 `edge` 프로바이더는 보이스가 적고 고정되어 있어(ko-KR은
> 3개뿐), 한국어 회의에서 4번째 이후 프로필은 보이스를 재사용합니다(설계상). 더 다양한
> 보이스가 필요하면 키 기반 프로바이더(`openai`, `gemini`, `elevenlabs`)를 쓰세요.

**Turns (턴 수)** _(기본 4)_ — 총 발언 턴. **참가자의 실질 답변과 모더레이터 최종
종합만** 카운트되며, 라우팅·메타·재시도·사용자 개입은 세지 않습니다.

**추천 조합**

- 일반 회의: `mixed` + `auto` _(기본)_ — 자연스러운 다단계 토론.
- 빠른 의견 수집: `parallel` + `auto`.
- 정밀 통제 / 시연: `sequential` + `manual`.
- 단발 전문가 질의: `directed`.

> 턴당 ~1분(추론 모델)이므로 `sequential` × 많은 턴 × 많은 인원은 수 분이 걸릴 수
> 있습니다. 빠르게 하려면 `parallel`이나 적은 턴 수를 쓰세요.

---

## 슬래시 명령 스왑

Slack은 앱당 슬래시 명령을 최대 50개까지 허용합니다. 자리를 만들기 위해 안 쓰는
기본 명령 2개를 빼고 같은 수를 추가합니다 — 총 개수는 그대로:

| 기능    | 제거됨     | 추가됨     |
| ------- | ---------- | ---------- |
| board   | `/footer`  | `/board`   |
| meeting | `/sethome` | `/meeting` |

제거된 명령도 Hermes 디스패처로 계속 동작합니다: `/hermes footer`,
`/hermes sethome`. 제거 목록은 `slash_dropped`로 기록됩니다.

---

## 진단 & 제거

```bash
hermes-ext uninstall --dry-run                 # 롤백 계획만 출력
hermes-ext uninstall --yes                     # 확인 없이 롤백
hermes-ext uninstall --yes --delete-apps       # 생성한 참가자 앱도 삭제
```

제거는 설치의 역순입니다: ① 클린 백업에서 `slack.py` 복원(언패치) → ② 오버레이
모듈 제거 → ③ 회의 산출물 정리(세션 스토어, 멘션 맵, 참가자 사이드카, 기본
매니페스트, 모더레이터 스킬, 스테이징) → ④ (`--delete-apps`) `apps.manifest.delete`로
생성한 앱 삭제.

- **토큰 규칙**: 앱 삭제용 config 토큰은 `HSE_CONFIG_TOKEN` 환경변수나 대화형 비밀
  입력으로만 받습니다 — CLI 인자나 로그에는 절대 들어가지 않습니다. 토큰이 없으면
  삭제를 건너뛰고 수동으로 지울 `app_id`를 출력합니다.
- 각 프로필의 `.env`(봇/앱 토큰)는 기본적으로 **보존**됩니다.
- 기본 앱의 슬래시 스왑 되돌리기는 수동 안내입니다(원본 매니페스트 스냅샷이 필요).
  `doctor`가 제거된 명령을 보고합니다.

제거 후 게이트웨이를 재시작하세요.

---

## 문제 해결

| 증상                                        | 원인 / 해결                                                                                                                                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| auto 라우팅에서 특정 참가자가 호출되지 않음 | 모든 봇이 패치된 게이트웨이 코드 **그리고** 자신의 `HERMES_HOME`에 `meeting_mentions.json` 멘션 맵을 가져야 합니다. 프로필이 별도 컨테이너로 실행되면 각각에 패치 + 맵을 배포하세요. |
| 모더레이터가 옛 메시지 형식을 계속 씀       | 에이전트 **세션이 영속**되어 재시작에도 resume됩니다. 세션을 리셋(`/new`, 또는 `HERMES_HOME/sessions/sessions.json` 비우기)해야 현재 프롬프트/스킬이 적용됩니다.                     |
| `/board` 또는 `/meeting`이 전달 안 됨       | 명령이 매니페스트에 선언되고 Socket Mode가 연결돼 있어야 합니다. 매니페스트와 `hermes-ext doctor`를 확인하세요.                                                                      |
| 봇끼리 응답하지 않음                        | 각 프로필의 `.env`에 `SLACK_ALLOW_BOTS=mentions`가 필요하고 봇이 채널에 있어야 합니다.                                                                                               |

---

## 기여자용

검증은 3단계로 진행됩니다.

- **L1 (단위)** — `pytest tests/ hermes_slack_ext` (Slack API·프롬프트 모킹).
- **L2 (헤드리스)** — `--answers-file`로 픽스처 Hermes 체크아웃에 위저드를
  엔드투엔드로 구동.
- **L3 (라이브)** — 실제 Slack 워크스페이스에 설치하고, 게이트웨이 로그가 아니라
  Slack Web API(`conversations.history`)로 동작을 검증.

---

## 라이선스

내부 도구 — 사용 전 워크스페이스 관리자와 확인하세요.
Copyright © 2026 Dante Labs.

---

<div align="center">

**YouTube** [@dante-labs](https://youtube.com/@dante-labs) · **Email** dante@dante-labs.com · [☕ Buy Me a Coffee](https://buymeacoffee.com/dante.labs)

</div>
