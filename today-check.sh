#!/bin/bash
# Today 할일 체크리스트 - 시스템 트레이 앱 실행 (중복 실행 방지)
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

if pgrep -f "python3.*tray.py" > /dev/null; then
    # 이미 실행 중이면 윈도우만 활성화
    wmctrl -a "오늘의 할일 체크리스트" 2>/dev/null || true
    exit 0
fi

python3 "${APP_DIR}/tray.py" &
