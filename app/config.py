import os
import secrets


def parse_minutes(value: str) -> int:
    """'9:00' / '08:15' / '540' -> minutes since midnight (or a duration in minutes)."""
    value = str(value).strip()
    if ":" in value:
        parts = value.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    return int(float(value))


class Settings:
    def __init__(self) -> None:
        self.username = os.getenv("HR_USERNAME", "kadry")
        self.password = os.getenv("HR_PASSWORD", "kadry")
        self.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
        self.session_hours = int(os.getenv("SESSION_HOURS", "12"))

        self.lunch_min = parse_minutes(os.getenv("LUNCH_MINUTES", "45"))
        self.arrival_start = parse_minutes(os.getenv("ARRIVAL_WINDOW_START", "08:00"))
        self.arrival_end = parse_minutes(os.getenv("ARRIVAL_WINDOW_END", "08:58"))
        self.required_week = parse_minutes(os.getenv("REQUIRED_PRESENCE_MON_THU", "9:02"))
        self.required_fri = parse_minutes(os.getenv("REQUIRED_PRESENCE_FRI", "7:47"))


settings = Settings()
