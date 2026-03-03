# Today Todo Checklist

A daily todo checklist app with GTK system tray integration for Linux.

## Features

- **System Tray** - Runs in background with status indicator (completed/total)
- **Dark Mode** - Full dark theme UI
- **Monthly Planner** - Calendar grid view with todo preview in each cell
- **Daily Recurring Tasks** - Register tasks that auto-populate every day
- **Per-Date Todos** - Manage separate todo lists for each date
- **Password Lock** - Optional password protection
- **Offline Support** - Service Worker caching for web version
- **Auto Launch** - Starts automatically on boot via autostart
- **Edit/Delete** - Edit button (✎) and delete button (✕) for each todo

## Requirements

- Python 3
- GTK 3
- AyatanaAppIndicator3

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
```

## Usage

### Run manually

```bash
./today-check.sh
```

### Auto start

The app auto-launches on boot via `~/.config/autostart/today-check.desktop`.

### Desktop shortcut

Double-click the "할일 체크리스트" icon on the desktop.

## Tech Stack

- Python 3 + GTK 3 (tray app)
- HTML / CSS / Vanilla JavaScript (web version)
- Service Worker (offline caching)

## Data

All data is stored in `~/.local/share/today-check/data.json`.
