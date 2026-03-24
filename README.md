# BBC Alert

A macOS menubar app that plays the BBC News jingle a configurable time before your Google Calendar meetings.

Inspired by [@rtwlz](https://x.com/rtwlz/status/2036082537949434164).

![menubar screenshot placeholder](https://via.placeholder.com/400x200?text=menubar+screenshot)

---

## Requirements

- macOS 12+
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — dependency manager
- [Homebrew](https://brew.sh/)
- Google Calendar synced to macOS Calendar

---

## Setup

### 1. Add Google Calendar to macOS

BBC Alert reads your calendar through macOS — no GCP setup or API keys required.

Go to **System Settings → Internet Accounts → Add Account → Google**, sign in, and make sure **Calendars** is enabled. Your Google Calendar events will now sync to the macOS Calendar app.

### 2. Clone and install dependencies

```bash
git clone https://github.com/your-username/bbc-alert.git
cd bbc-alert
brew install uv
uv sync
```

### 3. Download the BBC News jingle

Requires `ffmpeg` for audio transcoding:

```bash
brew install ffmpeg
uv run python src/download_audio.py
```

This downloads the BBC News countdown theme from YouTube and saves it to `assets/bbc_news.mp3`. Only needs to run once.

> If the download fails, the YouTube URL may have changed. Open `download_audio.py` and update `BBC_YOUTUBE_URL` with a working link.

### 4. Run the app

```bash
uv run python src/app.py
```

A `📻` icon appears in your menubar. Click **Grant Calendar Access** — macOS will show a standard permission dialog. After approving, your meetings for today will populate the menu.

---

## Usage

Click the `📻` menubar icon to open the menu:

```
📻
├── 09:00 — Standup (in 4 min)
├── 10:30 — Design review (in 95 min)
├── ─────
├── Alert: 5 minutes before       ← click to change
├── Test alert
├── Launch at login
├── ─────
├── ✅ Calendar access granted
└── Quit
```

**Changing alert timing** — click "Alert: X before" and type a duration:
- `15s` — 15 seconds
- `2m` — 2 minutes
- `10m` — 10 minutes (default is 5m, max is 15m)

**Test alert** — plays the jingle immediately to verify audio is working.

**Launch at login** — installs a LaunchAgent so the app starts automatically when you log in. Requires the app to be installed at `/Applications/BBC Alert.app` (see Build section below).

---

## Build a standalone .app bundle

To run as a proper macOS app (no terminal required) and enable launch at login:

```bash
# Make sure assets/bbc_news.mp3 exists first (run download_audio.py)
uv run python setup.py py2app
mv dist/BBC\ Alert.app /Applications/
open /Applications/BBC\ Alert.app
```

Then click **Launch at login** in the menubar menu. BBC Alert will now start automatically every time you log in.

> For faster iteration during development, use an alias build (symlinks instead of copies):
> ```bash
> uv run python setup.py py2app -A
> ```

---

## Data & privacy

All data stays on your machine:

| File | Contents |
|---|---|
| `~/.bbc-alert/prefs.json` | Alert timing preference |
| `~/.bbc-alert/alerted.json` | Events already alerted (prevents duplicate alerts, purged after 24h) |

---

## Troubleshooting

**Menubar icon doesn't appear**
Make sure you're running on macOS and that `rumps` installed correctly: `uv run python -c "import rumps"`.

**"Audio file missing" when testing**
Run `uv run python src/download_audio.py` first.

**Meetings don't show up**
Click the menubar icon — if it says "Grant Calendar Access", click it to trigger the macOS permission dialog. If it already says "✅ Calendar access granted", make sure your Google account is added under System Settings → Internet Accounts and Calendars is enabled.

**Download fails in download_audio.py**
The YouTube URL may be stale. Update `BBC_YOUTUBE_URL` in `download_audio.py` with a working link to the BBC News theme.

---

## Stack

- [rumps](https://github.com/jaredks/rumps) — macOS menubar apps in Python
- [pyobjc-framework-EventKit](https://pyobjc.readthedocs.io/) — native macOS calendar access
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — audio download
- [py2app](https://py2app.readthedocs.io/) — `.app` bundle packaging
- [uv](https://docs.astral.sh/uv/) — dependency management
