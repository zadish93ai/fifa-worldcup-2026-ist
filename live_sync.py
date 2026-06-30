"""Fetch live World Cup scores and regenerate the IST calendar."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from calendar_generator import DEFAULT_OUTPUT, DEFAULT_SCHEDULE_PATH, generate_ics, load_schedule

OPENFOOTBALL_URL = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
)
FOOTBALL_DATA_URL = "https://api.football-data.org/v4/competitions/WC/matches?season=2026"

TEAM_ALIASES = {
    "bosnia & herzegovina": "Bosnia and Herzegovina",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "cape verde": "Cape Verde",
    "congo dr": "Congo DR",
    "cote d'ivoire": "Ivory Coast",
    "côte d'ivoire": "Ivory Coast",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "dr congo": "Congo DR",
    "ivory coast": "Ivory Coast",
    "korea republic": "South Korea",
    "south korea": "South Korea",
    "turkey": "Türkiye",
    "türkiye": "Türkiye",
    "united states": "USA",
    "usa": "USA",
}


def normalize_team(name: str) -> str:
    key = re.sub(r"\s+", " ", name.strip().lower())
    return TEAM_ALIASES.get(key, name.strip())


def team_pair_key(date: str, team_a: str, team_b: str) -> tuple[str, tuple[str, str]]:
    teams = sorted([normalize_team(team_a), normalize_team(team_b)])
    return date, tuple(teams)


def build_schedule_lookup(schedule: dict) -> dict[tuple[str, tuple[str, str]], dict]:
    lookup: dict[tuple[str, tuple[str, str]], dict] = {}
    for row in schedule["matches"]:
        key = team_pair_key(row["date"], row["home"], row["away"])
        lookup[key] = row
    return lookup


def map_scores_to_home_away(
    home_team: str,
    away_team: str,
    first_team: str,
    first_score: int,
    second_score: int,
) -> tuple[int, int]:
    first = normalize_team(first_team)
    home = normalize_team(home_team)
    if first == home:
        return first_score, second_score
    return second_score, first_score


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict | list:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def scores_from_openfootball(schedule: dict) -> dict[int, tuple[int, int]]:
    try:
        payload = fetch_json(OPENFOOTBALL_URL)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"openfootball feed unavailable: {exc}", file=sys.stderr)
        return {}

    lookup = build_schedule_lookup(schedule)
    completed: dict[int, tuple[int, int]] = {}

    for match in payload.get("matches", []):
        match_number = match.get("num")
        
        if match_number is not None:
            match_number = int(match_number)
            row = next((item for item in schedule["matches"] if item["match_number"] == match_number), None)
            
            # AUTOMATED KNOCKOUT RETROFIT & TRACKING
            if row and 73 <= match_number <= 104:
                api_team1 = normalize_team(match.get("team1", ""))
                api_team2 = normalize_team(match.get("team2", ""))
                
                if api_team1 and api_team2:
                    # Overwrite placeholders if found in the schedule row
                    if any(p in row["home"] for p in ["Winners", "Runners-up", "Winner match"]):
                        row["home"] = api_team1
                        print(f"Auto-resolved Match {match_number} Home -> {api_team1}")
                    if any(p in row["away"] for p in ["Winners", "Runners-up", "Winner match"]):
                        row["away"] = api_team2
                        print(f"Auto-resolved Match {match_number} Away -> {api_team2}")
            
            if row:
                home_team, away_team = row["home"], row["away"]
            else:
                continue
        else:
            # Fallback to team pairing lookup for standard group stage games
            key = team_pair_key(match["date"], match["team1"], match["team2"])
            row = lookup.get(key)
            if row is None:
                continue
            match_number = row["match_number"]
            home_team, away_team = row["home"], row["away"]

        # Only extract the final score if the match is actually finished
        score = match.get("score", {}).get("ft")
        if score and len(score) == 2:
            completed[match_number] = map_scores_to_home_away(
                home_team,
                away_team,
                match["team1"],
                int(score[0]),
                int(score[1]),
            )

    return completed


def scores_from_football_data(schedule: dict, api_key: str) -> dict[int, tuple[int, int]]:
    if not api_key.strip():
        return {}

    try:
        payload = fetch_json(
            FOOTBALL_DATA_URL,
            headers={"X-Auth-Token": api_key},
        )
    except urllib.error.HTTPError as exc:
        print(f"football-data.org request failed: HTTP {exc.code}", file=sys.stderr)
        return {}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"football-data.org feed unavailable: {exc}", file=sys.stderr)
        return {}

    lookup = build_schedule_lookup(schedule)
    completed: dict[int, tuple[int, int]] = {}

    for match in payload.get("matches", []):
        home_name = normalize_team(match.get("homeTeam", {}).get("name", ""))
        away_name = normalize_team(match.get("awayTeam", {}).get("name", ""))
        utc_date = match.get("utcDate", "")[:10]
        
        # Check if the API explicitly includes a match number parameter
        api_match_no = match.get("matchNumber")

        row = None
        if api_match_no:
            row = next((item for item in schedule["matches"] if item["match_number"] == int(api_match_no)), None)
        if row is None:
            row = lookup.get(team_pair_key(utc_date, home_name, away_name))
            
        if row is None:
            continue

        match_number = row["match_number"]
        
        # AUTOMATED KNOCKOUT OVERWRITE FOR FOOTBALL-DATA
        if 73 <= match_number <= 104:
            if home_name and any(p in row["home"] for p in ["Winners", "Runners-up", "Winner match"]):
                row["home"] = home_name
                print(f"football-data auto-resolved Match {match_number} Home -> {home_name}")
            if away_name and any(p in row["away"] for p in ["Winners", "Runners-up", "Winner match"]):
                row["away"] = away_name
                print(f"football-data auto-resolved Match {match_number} Away -> {away_name}")

        # Extract scores only if the status indicates completion
        if match.get("status") == "FINISHED":
            full_time = match.get("score", {}).get("fullTime", {})
            home_score = full_time.get("home")
            away_score = full_time.get("away")
            if home_score is not None and away_score is not None:
                completed[match_number] = (int(home_score), int(away_score))

    return completed


def merge_completed_scores(*sources: dict[int, tuple[int, int]]) -> dict[str, list[int]]:
    merged: dict[int, tuple[int, int]] = {}
    for source in sources:
        merged.update(source)
    return {str(match_no): [home, away] for match_no, (home, away) in sorted(merged.items())}


def save_schedule(schedule: dict, path: Path = DEFAULT_SCHEDULE_PATH) -> None:
    path.write_text(json.dumps(schedule, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sync_and_generate(
    schedule_path: Path = DEFAULT_SCHEDULE_PATH,
    output_path: Path = DEFAULT_OUTPUT,
) -> tuple[dict[str, list[int]], list[dict]]:
    schedule = load_schedule(schedule_path)

    openfootball_scores = scores_from_openfootball(schedule)
    print(f"openfootball: {len(openfootball_scores)} finished matches")

    football_data_scores: dict[int, tuple[int, int]] = {}
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "").strip()
    if api_key:
        football_data_scores = scores_from_football_data(schedule, api_key)
        print(f"football-data.org: {len(football_data_scores)} finished matches")
    else:
        print("API key skipped, using openfootball fallback")

    schedule["completed_scores"] = merge_completed_scores(
        openfootball_scores,
        football_data_scores,
    )
    save_schedule(schedule, schedule_path)

    _, matches = generate_ics(schedule_path, output_path)
    return schedule["completed_scores"], matches


def main() -> None:
    completed_scores, matches = sync_and_generate()
    finished = len(completed_scores)
    print(f"Updated calendar with {finished} completed match(es) out of {len(matches)} total")
    print(f"Wrote {DEFAULT_OUTPUT.name}")


if __name__ == "__main__":
    main()
