"""CLI-specific configuration (not part of the anisama core library)."""

PLAYER_PATHS = {
    "Windows": {
        "mpv": [
            "mpv.exe",
            r"C:\Program Files\mpv\mpv.exe",
            r"C:\Program Files (x86)\mpv\mpv.exe",
            r"C:\Program Files\MPV Player\mpv.exe",
            r"C:\Program Files (x86)\MPV Player\mpv.exe",
        ],
        "vlc": [
            "vlc.exe",
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ],
        "iina": [],
        "moonplayer": [
            "moonplayer.exe",
            r"C:\Program Files\MoonPlayer\moonplayer.exe",
        ],
        "implay": [
            "ImPlay.exe",
            r"C:\Program Files\ImPlay\ImPlay.exe",
        ],
    },
    "Linux": {
        "mpv": ["mpv"],
        "vlc": ["vlc"],
        "iina": [],
        "moonplayer": ["moonplayer"],
        "implay": ["ImPlay"],
    },
    "Darwin": {
        "mpv": ["mpv"],
        "vlc": ["vlc"],
        "iina": ["iina"],
        "moonplayer": ["moonplayer"],
        "implay": ["ImPlay"],
    },
}
