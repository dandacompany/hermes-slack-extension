#!/usr/bin/env bash
# hermes-slack-extension bootstrap: 격리 venv 생성 → 패키지 설치 → hermes-ext 실행
set -euo pipefail

REPO="${HSE_REPO:-https://github.com/dandacompany/hermes-slack-extension}"
REF="${HSE_REF:-main}"
HOME_DIR="${HSE_HOME:-$HOME/.hermes/hermes-slack-ext}"
VENV="$HOME_DIR/venv"

echo "[hse] target home: $HOME_DIR"
mkdir -p "$HOME_DIR"

if [ ! -d "$VENV" ]; then
  echo "[hse] creating venv"
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
echo "[hse] installing hermes-slack-extension@$REF"
"$VENV/bin/pip" install --quiet "git+$REPO@$REF"

# 영속 명령 등록 (~/.local/bin/hermes-ext → venv 콘솔스크립트)
BIN_DIR="${HSE_BIN:-$HOME/.local/bin}"
mkdir -p "$BIN_DIR"
ln -sf "$VENV/bin/hermes-ext" "$BIN_DIR/hermes-ext"
echo "[hse] linked $BIN_DIR/hermes-ext"

echo "[hse] launching wizard"
exec "$VENV/bin/hermes-ext" install "$@"
