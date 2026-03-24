"""
py2app build configuration for BBC Alert.

Alias build (fast, for development — uses symlinks):
    uv run python setup.py py2app -A

Full build (standalone .app bundle for distribution):
    uv run python setup.py py2app

The resulting .app will be at dist/BBC Alert.app.
Move it to /Applications/ for launch-at-login to work.
"""

import os
from setuptools import setup

data_files = []

if os.path.exists("assets/bbc_news.mp3"):
    data_files.append(("assets", ["assets/bbc_news.mp3"]))

OPTIONS = {
    # CRITICAL: argv_emulation must be False for rumps.
    # True causes the app to silently hang on launch.
    "argv_emulation": False,
    "packages": [
        "rumps",
    ],
    "includes": [
        "src.calendar_client",
        "src.scheduler",
        "EventKit",
        "Foundation",
    ],
    "frameworks": [],
    "plist": {
        # No dock icon — this is a menubar-only app.
        "LSUIElement": True,
        "CFBundleName": "BBC Alert",
        "CFBundleDisplayName": "BBC Alert",
        "CFBundleIdentifier": "com.bbc-alert",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSHumanReadableCopyright": "Personal use",
        # Required for macOS to show the calendar permission dialog.
        "NSCalendarsUsageDescription": (
            "BBC Alert reads your calendar to play the BBC News jingle "
            "before upcoming meetings."
        ),
    },
    "iconfile": None,  # Set to "assets/icon.icns" if you have one
}

setup(
    name="BBC Alert",
    app=["src/app.py"],
    data_files=data_files,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
