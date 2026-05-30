# hermes-slack-extension

Hermes Agent(0.15.x)의 Slack 연동에 **`/board` 칸반 보드**와 **`/meeting` 텍스트 회의룸**을
결정론적으로 추가하는 CLI 설치 마법사입니다. 비결정적 스킬 방식을 대체해, 같은 입력이면
항상 같은 결과를 만듭니다. 대화형 TUI로 한 단계씩 묻거나, `--answers-file`로 헤드리스 실행할 수 있습니다.

## 무엇을 하나

- **`/board`** — Hermes의 `gateway/platforms/slack.py`에 칸반 보드 Block Kit 핸들러를 멱등(idempotent)
  패치하고 보드 오버레이 모듈을 설치합니다.
- **`/meeting`** — 프로필별 Slack 앱(참가자)을 자동 생성하고, 페르소나 매트릭스·채널 프롬프트·
  bot-to-bot 배선·모더레이터 스킬을 구성해 텍스트 구동 회의룸을 만듭니다.
- **슬래시 스왑** — Slack의 슬래시 명령 50개 한도 안에서, 잘 쓰지 않는 기본 명령 2개를 빼고
  `/board`·`/meeting`을 넣습니다(아래 참고). 빠진 명령은 그대로 사라지지 않고 `/hermes <명령>`으로 동작합니다.
- **매니페스트 자동 생성** — 설치된 Hermes의 `hermes slack manifest`를 그대로 호출해
  현재 버전의 명령 레지스트리를 반영한 매니페스트를 만들고, 거기에 스왑을 적용합니다.
  Socket Mode·interactivity는 매니페스트에서 자동 활성화되어 사용자가 따로 켤 필요가 없습니다.

## 설치

```bash
# 부트스트랩 (격리 venv + hermes-ext 등록)
curl -fsSL <install-remote.sh URL> | bash

# 또는 직접
pip install git+<repo>
hermes-ext install            # 대화형 마법사
```

마법사는 Hermes 루트(기본 `~/.hermes/hermes-agent`)를 감지하고, 지원 버전(0.12.0~0.15.1)인지
확인한 뒤 기능을 선택받아 단계별로 진행합니다.

```
hermes-ext install \
  --hermes-root ~/.hermes/hermes-agent \
  --answers-file answers.yaml \   # 헤드리스(선택)
  --non-interactive \
  --dry-run                       # 변경 없이 시뮬레이션(선택)
```

## `/meeting` 설치 흐름

미팅 기능을 선택하면 마법사가 다음 순서로 진행합니다.

1. **회의 프로필 구성** — 기본 4세트(Moderator·Researcher·Developer·Designer) 그대로 수용하거나,
   프리셋 선택/커스텀으로 이름·페르소나까지 바꿀 수 있습니다(LLM 추론 없음, 전부 결정론적).
   - 모더레이터 = 사용자의 **기존 베이스 Hermes 앱**(슬래시 스왑으로 `/meeting` 추가).
   - 참가자 3명 = 신규로 만드는 **최소 매니페스트 앱**(슬래시 명령 없음, Socket Mode on).
2. **App Configuration Token 캡처** — `api.slack.com/apps` → *Your App Configuration Tokens*에서
   발급한 토큰(+refresh)을 입력합니다. 토큰 1개가 워크스페이스의 모든 앱을 만듭니다.
   입력값은 화면에 노출되지 않고 마스킹된 확인만 표시됩니다.
3. **참가자 앱 생성·토큰** — 프로필마다 `apps.manifest.create`로 앱을 만들고, 사용자가 수동으로
   설치(OAuth) 후 받은 Bot Token·App-Level Token을 붙여넣습니다. 토큰은 프로필별 `.env`에
   `0600`으로 원자적 기록되며, `auth.test`로 `bot_user_id`를 자동 획득하고 공개 채널이면 봇을 초대합니다.
4. **모더레이터 베이스 앱 적용** — config 토큰 + 베이스 `app_id`가 있으면 `apps.manifest.update`로
   스왑된 매니페스트를 적용하고, 없으면 매니페스트 파일 경로를 안내해 수동 적용하도록 합니다.
5. **배선** — 각 프로필 `.env`에 bot-to-bot 환경변수(`SLACK_ALLOWED_USERS`에 모든 봇 포함,
   `SLACK_ALLOW_BOTS=mentions` 등)를 기록하고, 모더레이터·참가자 채널 프롬프트를 스테이징
   디렉터리에 렌더하며, 모더레이터 스킬을 `~/.hermes/skills/hermes-meeting/`에 설치합니다.

### 사용자가 직접 해야 하는 수동 단계

자동화할 수 없는 항목(Slack UI/OAuth 제약)은 마법사가 안내합니다.

- **App Configuration Token 발급** — `api.slack.com/apps`의 _Your App Configuration Tokens_.
- **각 참가자 앱 설치(Install to Workspace)** — OAuth로 Bot Token(`xoxb-…`) 발급.
- **App-Level Token 발급** — `connections:write` 스코프(`xapp-…`). API로는 만들 수 없어 UI에서 발급.
- **채널에 봇 초대** — 비공개 채널이거나 자동 초대가 막힌 경우.

대화형 실행 시 마법사가 아래 식별자(비밀 아님)를 묻습니다. 헤드리스(`--answers-file`)는
같은 키로 미리 제공합니다.

- **회의 채널 ID**(`channel_id`, `Cxxxxxxxx`) — 참가자 봇 자동 초대·배선 대상.
- **본인 Slack User ID**(`human_user_id`, `Uxxxxxxxx`) — allow-list에 포함.
- **모더레이터 Bot User ID**(`moderator_bot_user_id`, `Uxxxxxxxx`) — 베이스 Hermes 앱의 봇.
  이 값이 있어야 모더레이터가 `SLACK_ALLOWED_USERS`에 포함되어 모더레이터→참가자
  멘션 라우팅이 동작합니다(누락 시 참가자가 모더레이터 멘션을 무시).

> 봇/앱 토큰은 마법사가 절대 출력하지 않으며, 프로필별 `.env`에만 `0600`으로 저장됩니다.
> `--dry-run`은 실제 Slack 앱을 만들거나 토큰을 기록하지 않고 수행 계획만 보여줍니다.

## 슬래시 명령 스왑

Slack 워크스페이스 앱당 슬래시 명령은 최대 50개입니다. 확장은 자리를 만들기 위해
기본 명령에서 2개를 빼고 같은 수만큼 넣어 **총개수를 유지**합니다.

| 기능    | 빠지는 기본 명령 | 추가되는 명령 |
| ------- | ---------------- | ------------- |
| board   | `/footer`        | `/board`      |
| meeting | `/sethome`       | `/meeting`    |

빠진 명령은 기능을 잃지 않습니다. Hermes의 디스패처(`/hermes <명령>`)로 그대로 호출할 수 있습니다
(예: `/hermes footer`). 빠진 목록은 설치 상태에 `slash_dropped`로 기록됩니다.

## 검증 단계

- **L1(코드)** — `pytest` 단위 테스트. Slack API·토큰 프롬프트는 모두 목으로 처리.
- **L2(헤드리스)** — 실 Hermes 체크아웃을 복제해 `--answers-file`로 마법사를 끝까지 구동
  (`tests/e2e/test_headless_meeting_setup.py`). Slack API는 목, 실 토큰 불필요.
- **L3(실 Slack, 토큰 필요)** — 아래 체크리스트. 이 단계에서만 실제 토큰을 사용합니다.

### L3 스모크 체크리스트

1. config 토큰 + 참가자 토큰으로 실제 앱 생성·설치·초대까지 마법사 완주.
2. 게이트웨이 재시작: `hermes gateway restart`.
3. 회의 채널에서 `/meeting <주제>` 텍스트 호출 → 모더레이터가 setup 초안(참가자·진행 방식)을 제시.
4. 참가자 봇들이 멘션 기반으로 응답하며 bot-to-bot 대화가 도는지 확인.

## 로드맵

- **P3** — Block Kit 기반 `/meeting` 런타임(`slack_meeting_room.py` 등, 보드 패턴 미러링).
- **P4** — `hermes-ext uninstall`/`doctor`(생성 앱·패치·env 원복), L3 자동 스모크.

## 라이선스

내부 도구. 사용 전 워크스페이스 관리자 승인 필요.
