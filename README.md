# BBC Alert

A macOS menubar app that plays the BBC News jingle 15 seconds before your Google Calendar meetings, with a live countdown in the menubar.

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

> If the download fails, the YouTube URL may have changed. Open `src/download_audio.py` and update `BBC_YOUTUBE_URL` with a working link.

### 4. Run the app

```bash
uv run python src/app.py
```

The broadcast clock icon (`assets/icon.svg`) appears in your menubar. Click **Grant Calendar Access** — macOS will show a standard permission dialog. After approving, your meetings for today will populate the menu.

---

## Usage

Click the menubar icon to open the menu:

```
[icon]
├── 09:00 — Standup (in 4 min)
├── 10:30 — Design review (in 95 min)
├── ─────
├── Test alert
├── Silence
├── Launch at login
├── ─────
├── ✅ Calendar access granted
└── Quit
```

**Countdown behaviour** — 15 seconds before a meeting the menubar title changes to show a live countdown:

| Time to meeting | Menubar |
|---|---|
| > 15s | icon only |
| 11–15s | `<Standup> in 14s` |
| 6–10s | `<Standup> in 8s` — red background flashes 1×/sec |
| 1–5s | `<Standup> in 3s` — red background flashes 2×/sec |
| 0s | `<Standup> is live!` (shown for 4 seconds) |

**Test alert** — plays the jingle and runs the full 15-second countdown so you can see how it looks and sounds.

**Silence** — stops the audio immediately if it's playing.

**Launch at login** — installs a LaunchAgent so the app starts automatically when you log in. Requires the app to be installed at `/Applications/BBC Alert.app` (see Build section below).

---

## Icon

The menubar icon (`assets/icon.svg`) is a broadcast clock — a clock face showing 11:00 with radio wave arcs on each side. It's a [template image](https://developer.apple.com/design/human-interface-guidelines/menus#Menu-bar-extras) so macOS automatically renders it white in dark mode and black in light mode.

To customise it, edit `assets/icon.svg` and restart the app.

---

## Build a standalone .app bundle

To run as a proper macOS app (no terminal required) and enable launch at login:

```bash
# Make sure assets/bbc_news.mp3 exists first (run src/download_audio.py)
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
| `~/.bbc-alert/alerted.json` | Events already alerted (prevents duplicate alerts, purged after 24h) |

---

## Troubleshooting

**Menubar shows "BBC Alert" text instead of icon**
Make sure `assets/icon.svg` exists. If it's missing, re-clone the repo.

**Menubar icon doesn't appear at all**
Make sure you're running on macOS and that `rumps` installed correctly: `uv run python -c "import rumps"`.

**"Audio file missing" when testing**
Run `uv run python src/download_audio.py` first.

**Meetings don't show up**
Click the menubar icon — if it says "Grant Calendar Access", click it to trigger the macOS permission dialog. If it already says "✅ Calendar access granted", make sure your Google account is added under System Settings → Internet Accounts and Calendars is enabled.

**Download fails in download_audio.py**
The YouTube URL may be stale. Update `BBC_YOUTUBE_URL` in `src/download_audio.py` with a working link to the BBC News theme.

---

## Stack

- [rumps](https://github.com/jaredks/rumps) — macOS menubar apps in Python
- [pyobjc-framework-EventKit](https://pyobjc.readthedocs.io/) — native macOS calendar access
- [pyobjc-framework-Quartz](https://pyobjc.readthedocs.io/) — CALayer red flash background
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — audio download
- [py2app](https://py2app.readthedocs.io/) — `.app` bundle packaging
- [uv](https://docs.astral.sh/uv/) — dependency management
