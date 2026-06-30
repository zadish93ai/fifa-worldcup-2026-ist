# AI Context — FIFA World Cup 2026 IST Calendar

> **Purpose:** This file gives AI assistants and contributors a fast, accurate mental model of the repository. Read this before making changes.

---

## Overview

This project generates and maintains a **live-syncing iCalendar (`.ics`) file** for all **104 matches** of the **FIFA World Cup 2026** (June 11 – July 19, 2026), hosted across **16 stadiums** in Canada, Mexico, and the United States.

**Primary goal:** Let users subscribe once to a calendar that shows every match in **Indian Standard Time (IST)** and automatically updates event titles with **final scores** as games finish.

**Distribution:** The calendar is published via GitHub Pages:

```text
https://zadish93ai.github.io/fifa-worldcup-2026-ist/world_cup_live_ist.ics
```

**Automation:** A GitHub Actions workflow runs every **3 hours**, fetches live score data from public sports feeds, regenerates the `.ics` file, and commits changes back to the repo so subscribed calendar apps pick up updates.

**Target audience:** Indian fans (IST timezone) who want zero-maintenance World Cup scheduling on Google Calendar, Apple Calendar, Outlook, etc.

---

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Language | Python **3.14** | Pinned in `.python-version` |
| Package manager | **uv** only | Never use `pip` or `conda` |
| Lock file | `uv.lock` | CI uses `uv sync --frozen` |
| Calendar library | `ics` ≥ 0.7.3 | Builds `.ics` events |
| Timezone library | `pytz` ≥ 2026.2 | Stadium local → IST conversion |
| Notebook | `jupyter` ≥ 1.1.1 | Interactive dev via `live_generator.ipynb` |
| HTTP (stdlib) | `urllib.request` | No `requests` dependency for live sync |
| CI/CD | GitHub Actions | `astral-sh/setup-uv@v5` on `ubuntu-latest` |
| Hosting | GitHub Pages | Serves committed `world_cup_live_ist.ics` |
| Data feeds | openfootball (primary), football-data.org (optional) | See [Live Score Sources](#live-score-sources) |

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `FOOTBALL_DATA_API_KEY` | No | Optional faster live scores via [football-data.org](https://www.football-data.org/). If unset, script prints `API key skipped, using openfootball fallback` and continues. |

---

## File Structure

```text
fifa-worldcup-2026-ist/
├── AI_CONTEXT.md                  # This file — AI/contributor context
├── README.md                      # User-facing subscribe instructions
├── .cursorrules                   # Cursor AI project rules (uv, IST, live scores)
├── .python-version                # 3.14
├── pyproject.toml                 # Project metadata + dependencies
├── uv.lock                        # Locked dependency versions
│
├── calendar_generator.py          # Core: schedule → IST events → .ics
├── live_sync.py                   # Fetches live scores, updates schedule, regenerates .ics
├── main.py                        # CLI entry point (wraps live_sync)
├── live_generator.ipynb           # Jupyter notebook for manual generation
├── world_cup_live_ist.ics         # Generated output (committed + served via Pages)
│
├── data/
│   └── world_cup_2026_schedule.json   # Source of truth: 104 fixtures, stadiums, flags, scores
│
└── .github/
    └── workflows/
        └── update_calendar.yml    # Cron + manual workflow for automated updates
```

### Key Files — Responsibilities

| File | Role |
|------|------|
| `data/world_cup_2026_schedule.json` | Static fixture list (104 matches), 16 stadiums with IANA timezones, 48 team flag emojis, and mutable `completed_scores` overlay |
| `calendar_generator.py` | Pure generation logic — no network calls |
| `live_sync.py` | Network fetch → score merge → schedule save → calendar regenerate |
| `world_cup_live_ist.ics` | Deliverable consumed by calendar apps |
| `.github/workflows/update_calendar.yml` | Automated pipeline (every 3h UTC) |

---

## Core Logic

### Data Flow

```text
┌─────────────────────────────────────────────────────────────────┐
│  data/world_cup_2026_schedule.json                              │
│  (104 matches, stadiums, team_flags, completed_scores)          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │         live_sync.py              │
         │  1. Fetch openfootball JSON       │
         │  2. Optionally fetch football-data│
         │  3. Match by date + team names    │
         │  4. Write completed_scores        │
         └─────────────────┬─────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │      calendar_generator.py        │
         │  1. build_matches()               │
         │  2. stadium_time_to_ist()         │
         │  3. build_event_title()           │
         │  4. create_calendar()             │
         └─────────────────┬─────────────────┘
                           │
                           ▼
              world_cup_live_ist.ics
                           │
                           ▼
         GitHub Actions commit + push
                           │
                           ▼
              GitHub Pages → user calendars
```

### Schedule JSON Schema

```json
{
  "stadiums": {
    "Estadio Azteca": { "city": "Mexico City", "timezone": "America/Mexico_City" }
  },
  "team_flags": {
    "Mexico": "🇲🇽"
  },
  "completed_scores": {
    "1": [2, 1]
  },
  "matches": [
    {
      "match_number": 1,
      "date": "2026-06-11",
      "time": "13:00",
      "stadium": "Estadio Azteca",
      "home": "Mexico",
      "away": "South Africa"
    }
  ]
}
```

- **104 matches:** 72 group stage (1–72) + 32 knockout (73–104)
- **16 stadiums** across 3 countries, each with an IANA timezone
- **48 teams** with flag emoji mappings
- Knockout matches 73–104 use placeholder team names (e.g. `"Group A Winners"`, `"Match 97 Winner"`) — these get the default 🏳️ flag

### Timezone Conversion

```python
# calendar_generator.py → stadium_time_to_ist()
local_tz.localize(naive_datetime).astimezone(IST)
```

- Input: stadium-local `date` + `time` from JSON, resolved via `stadiums[stadium].timezone`
- Output: timezone-aware `datetime` in `Asia/Kolkata`
- Event duration: **2 hours** (start + `timedelta(hours=2)`)

**Example — Match 1:**
- Local: `2026-06-11 13:00` at Estadio Azteca (`America/Mexico_City`)
- IST: `2026-06-12 00:30 IST`

### Event Title Format

| Status | Format | Example |
|--------|--------|---------|
| Scheduled | `⚽ Match {n}: {home_flag} {home} vs {away} {away_flag}` | `⚽ Match 4: 🇺🇸 USA vs Paraguay 🇵🇾` |
| Completed | `🎯 Match {n}: {home_flag} {home} {home_score} - {away_score} {away} {away_flag} (FT)` | `🎯 Match 1: 🇲🇽 Mexico 2 - 1 South Africa 🇿🇦 (FT)` |

Status is derived from presence in `completed_scores`, not from an external API status field at generation time.

### Live Score Sources

#### 1. openfootball (primary, no API key)

- URL: `https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json`
- Finished matches include `score.ft: [home, away]`
- Group matches matched by `(date, sorted team pair)`; knockout by `num` field
- Community-maintained; may lag behind real-time

#### 2. football-data.org (optional, requires API key)

- URL: `https://api.football-data.org/v4/competitions/WC/matches?season=2026`
- Header: `X-Auth-Token: {FOOTBALL_DATA_API_KEY}`
- Only `status == "FINISHED"` matches are used
- Scores from `score.fullTime.home` / `score.fullTime.away`
- football-data.org scores **override** openfootball on conflict (merged last)

#### Team Name Normalization

`live_sync.py` maps API name variants to schedule names via `TEAM_ALIASES`:

- `Czech Republic` → `Czechia`
- `Turkey` → `Türkiye`
- `United States` → `USA`
- `DR Congo` → `Congo DR`
- `Ivory Coast` / `Côte d'Ivoire` → `Ivory Coast`
- etc.

Matching key: `(date, tuple(sorted(normalized_team_a, normalized_team_b)))`

### GitHub Actions Workflow

**File:** `.github/workflows/update_calendar.yml`

**Triggers:**
- Cron: `0 */3 * * *` (every 3 hours UTC)
- Manual: `workflow_dispatch`

**Steps:**
1. Checkout repo
2. Install uv + Python 3.14 via `astral-sh/setup-uv@v5`
3. `uv sync --frozen` — install locked deps
4. `uv run python live_sync.py` — fetch scores, regenerate calendar
5. Commit `world_cup_live_ist.ics` + `data/world_cup_2026_schedule.json` if changed, then push

**Permissions:** `contents: write` (required for bot commits)

**YAML gotcha:** Multiline strings inside `run: |` blocks must stay indented. Use `git commit -m "..." -m "..."` instead of unindented multiline quotes.

### Local Commands

```bash
# First-time setup
uv sync

# Regenerate calendar with live score fetch
uv run python live_sync.py

# Same via main entry point
uv run python main.py

# Interactive notebook
uv run jupyter notebook live_generator.ipynb
```

---

## Project Conventions

1. **Always use `uv`** — never recommend `pip` or `conda`
2. **All kickoff times → IST** — never store or display venue time as the calendar event time
3. **104 matches exactly** — `generate_ics()` raises `ValueError` if count ≠ 104
4. **Minimal dependencies** — prefer stdlib (`urllib`) over adding HTTP libraries
5. **Graceful degradation** — missing API key or feed failure must not crash the workflow
6. **Committed artifacts** — both `.ics` and updated `completed_scores` in JSON are committed by CI

---

## Next Steps

### High Priority

- [ ] **Resolve knockout placeholder titles dynamically** — as bracket results arrive, replace `"Match 97 Winner"` style names with actual team names in event titles
- [ ] **Add in-progress match status** — show live scores during matches (e.g. `(HT)`, `(67')`) not just `(FT)` for completed games
- [ ] **Validate openfootball sync during tournament** — monitor match mapping accuracy once real scores appear; extend `TEAM_ALIASES` as needed

### Medium Priority

- [ ] **Add tests** — unit tests for `stadium_time_to_ist`, `build_event_title`, team normalization, and score mapping
- [ ] **Reduce Jupyter dependency in CI** — move `jupyter` to optional/dev dependency group since production only needs `ics` + `pytz`
- [ ] **Stable event UIDs in `.ics`** — ensure calendar apps update existing events in-place rather than creating duplicates on refresh
- [ ] **GitHub Pages workflow** — explicit Pages deploy step if not already configured in repo settings

### Low Priority / Nice to Have

- [ ] **Group stage labels in descriptions** — add group letter (A–L) to event description field
- [ ] **CLI flags** — `--dry-run`, `--offline` (skip network, use existing scores), `--output path`
- [ ] **Rate limiting / retry** — exponential backoff for API fetches in CI
- [ ] **Notification hook** — optional webhook/Telegram alert when a major match finishes
- [ ] **Subscribe URL in repo** — add `webcal://` link variant in README for one-click mobile subscribe

### Known Limitations

- openfootball feed is community-updated and may be slower than commercial APIs
- football-data.org free tier has delayed scores; live scores require paid plan
- Calendar app refresh intervals vary (Apple Calendar: user-configurable; Google: ~12–24h for URL subscriptions)
- Knockout round fixtures use TBD placeholder names until teams are determined
- TheSportsDB free tier does not expose all 104 events reliably (not currently used)

---

## Quick Reference for AI Assistants

**When asked to add a feature:** Start in `live_sync.py` (data) or `calendar_generator.py` (presentation). Avoid duplicating logic in the notebook — notebook should call shared modules.

**When asked to fix CI:** Check `.github/workflows/update_calendar.yml` YAML indentation first, then verify `uv sync --frozen` and Python 3.14 availability.

**When asked to update fixtures:** Edit `data/world_cup_2026_schedule.json` only. Keep 104 matches, correct stadium timezones, and consistent team names with `team_flags` keys.

**When asked about timezones:** Stadium times in JSON are **local kickoff at venue**. Calendar events are always **IST**. Never hardcode UTC offsets — use IANA timezone names from the stadiums map.

---

*Last generated from codebase scan. Update this file when architecture or workflows change materially.*
