"""Generate a live-syncing FIFA World Cup 2026 calendar in IST."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from ics import Calendar, Event

IST = pytz.timezone("Asia/Kolkata")
DEFAULT_SCHEDULE_PATH = Path(__file__).parent / "data" / "world_cup_2026_schedule.json"
DEFAULT_OUTPUT = Path(__file__).parent / "world_cup_live_ist.ics"
DEFAULT_FLAG = "🏳️"


def load_schedule(path: Path = DEFAULT_SCHEDULE_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def flag_for(team: str, team_flags: dict[str, str]) -> str:
    return team_flags.get(team, DEFAULT_FLAG)


def stadium_time_to_ist(date: str, time: str, stadium_tz: str) -> datetime:
    local_tz = pytz.timezone(stadium_tz)
    naive = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    return local_tz.localize(naive).astimezone(IST)


def build_matches(schedule: dict) -> list[dict]:
    stadiums = schedule["stadiums"]
    team_flags = schedule["team_flags"]
    completed_scores = {
        int(k): tuple(v) for k, v in schedule.get("completed_scores", {}).items()
    }

    matches = []
    for row in schedule["matches"]:
        match_no = row["match_number"]
        stadium = row["stadium"]
        city = stadiums[stadium]["city"]
        timezone = stadiums[stadium]["timezone"]
        home = row["home"]
        away = row["away"]
        is_completed = match_no in completed_scores
        home_score, away_score = completed_scores.get(match_no, (None, None))

        matches.append(
            {
                "match_number": match_no,
                "date": row["date"],
                "time": row["time"],
                "timezone": timezone,
                "stadium": stadium,
                "city": city,
                "home_team": home,
                "home_flag": flag_for(home, team_flags),
                "away_team": away,
                "away_flag": flag_for(away, team_flags),
                "status": "Completed" if is_completed else "Scheduled",
                "home_score": home_score,
                "away_score": away_score,
            }
        )

    return matches


def build_event_title(match: dict) -> str:
    n = match["match_number"]
    home = f"{match['home_flag']} {match['home_team']}"
    away = f"{match['away_team']} {match['away_flag']}"

    if match["status"] == "Completed":
        return (
            f"🎯 Match {n}: {home} {match['home_score']} - "
            f"{match['away_score']} {away} (FT)"
        )

    return f"⚽ Match {n}: {home} vs {away}"


def create_calendar(matches: list[dict]) -> Calendar:
    calendar = Calendar()
    calendar.creator = "FIFA World Cup 2026 — Live IST Sync"

    for match in matches:
        start_ist = stadium_time_to_ist(match["date"], match["time"], match["timezone"])
        end_ist = start_ist + timedelta(hours=2)

        event = Event()
        event.name = build_event_title(match)
        event.begin = start_ist
        event.end = end_ist
        event.location = f"{match['stadium']}, {match['city']}"
        event.description = (
            f"Status: {match['status']}\n"
            f"Local: {match['date']} {match['time']} ({match['timezone']})\n"
            f"IST: {start_ist.strftime('%Y-%m-%d %H:%M %Z')}"
        )
        calendar.events.add(event)

    return calendar


def generate_ics(
    schedule_path: Path = DEFAULT_SCHEDULE_PATH,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[Calendar, list[dict]]:
    schedule = load_schedule(schedule_path)
    matches = build_matches(schedule)

    if len(matches) != 104:
        raise ValueError(f"Expected 104 matches, got {len(matches)}")

    calendar = create_calendar(matches)

    output_path.write_text("".join(calendar), encoding="utf-8")

    return calendar, matches
