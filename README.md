<div align="center">

<img src="static/app-icon.svg" width="96" alt="Switch Tracker icon">

# Switch Tracker

**Turn the play history scattered across your Nintendo account into a local game journal you control.**

**English** | [简体中文](README.zh-CN.md)

[Features](#features) · [Quick start](#quick-start) · [Design](#project-design) · [Roadmap](#roadmap) · [Contributing](#contributing)

</div>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

Switch Tracker is a local-first, non-commercial tool for collecting and visualizing Nintendo Switch playtime. Your data stays on your computer and is presented through a lightweight web dashboard with trends, game lists, recent activity, and calendar views.

## Why I built it

The play history built into Nintendo Switch is useful for a quick glance, but it is not designed for organizing or revisiting activity over time. I wanted to understand how much I played each month, which games I returned to most often, and—most importantly—to keep a copy of that history under my own control.

Switch Tracker grew from a personal script into a small local application. It remains an independently maintained project built in my spare time: the priorities come from real use, while installation, privacy, testing, and contribution workflows are treated as first-class parts of the project.

**Project status: under active development.** Core collection, SQLite storage, visualization, and local title translation are usable today. Nintendo API changes, cross-platform setup, and frontend testing remain areas for continued improvement. See [CHANGELOG.md](CHANGELOG.md) for completed work and [ROADMAP.md](ROADMAP.md) for planned directions.

> [!IMPORTANT]
> This is an unofficial community project. It is not affiliated with, authorized by, or endorsed by Nintendo. Nintendo may change the underlying interfaces at any time. Access only your own account data and make sure your use complies with applicable laws and terms of service.

## Features

- Collect total playtime and daily play records
- Update the same day idempotently, without double-counting repeated collections
- Explore overview, monthly trend, recent activity, game list, and calendar views
- Maintain localized game titles through a local CSV workflow
- Keep tokens, databases, logs, and raw responses out of Git by default
- Run a single reliable collection command from schedulers such as cron

## Screenshots

| Overview | Recent activity |
| --- | --- |
| ![Overview dashboard](pic/main.png) | ![Recent activity view](pic/recent.png) |

| Game calendar | Game list |
| --- | --- |
| ![Game calendar](pic/calender.png) | ![Game list](pic/game_list.png) |

## Quick start

Switch Tracker requires Python 3.9 or later.

```bash
git clone https://github.com/pengchzn/switch_tracker.git
cd switch_tracker

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Collect data for the first time:

```bash
python get_switch_data.py
```

The terminal will print a Nintendo sign-in URL. Sign in, select your account, and paste the callback URL back into the terminal. The session token is saved to `config/tokens.json` with permissions restricted to the current user.

Start the local dashboard:

```bash
python server.py
```

Open <http://127.0.0.1:8000>. The server listens only on the loopback interface by default and should not be exposed directly to the public internet.

## Scheduled collection

`daily_collect.py` performs one collection and returns a reliable exit code. It does not restart or manage the web server:

```bash
python daily_collect.py
```

Example cron entry:

```cron
0 23 * * * cd /path/to/switch_tracker && .venv/bin/python daily_collect.py
```

To retain raw API responses for debugging, enable archival explicitly:

```bash
python get_switch_data.py --archive-json
```

Raw responses may contain personal activity data, so they are not saved by default. The `history_data/` directory is also ignored by Git.

## Game title translation

```bash
python game_translation.py export
# Edit the chinese_name column in game_translations.csv
python game_translation.py import
```

Importing updates the database immediately. The legacy `apply` command remains available for compatibility.
To remove a translation, keep its CSV row and leave `chinese_name` empty, then import again. The dashboard falls back to the original name. Games omitted from the CSV are unchanged.

## Configuration

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `SWITCH_TRACKER_DB` | `./switch_tracker.db` | Use a custom SQLite database path |
| `SWITCH_TRACKER_HOST` | `127.0.0.1` | Set the web server bind address |
| `SWITCH_TRACKER_PORT` | `8000` | Set the web server port |
| `FLASK_DEBUG` | `0` | Set to `1` only during local development |
| `LOG_LEVEL` | `INFO` | Set the web server log level |

Binding to `0.0.0.0` allows other devices on the local network to connect. Configure a firewall or trusted reverse proxy first; the project does not currently provide user authentication.

## Project design

The project intentionally stays lightweight. Python handles authentication and collection, SQLite provides local persistence, Flask serves a read-only API, and the browser renders the dashboard. No external database or additional cloud account is required.

```text
Nintendo account
       │
       ▼
get_switch_data.py ──► tracker_db.py ──► SQLite
                                            │
                                            ▼
Browser dashboard ◄── JSON API ◄── server.py
```

The main design choices are:

- **Local first:** tokens and play history remain on the user's device by default.
- **Safe to repeat:** collecting the same day updates existing data instead of accumulating duplicates.
- **Conservative exposure:** the server binds locally and never serves the repository as its static root.
- **Small, maintainable stack:** Python, SQLite, and native JavaScript keep infrastructure to a minimum.

For module boundaries and a more detailed data flow, see [docs/architecture.md](docs/architecture.md).

## Data and privacy

- `config/tokens.json`: sensitive Nintendo session and access tokens
- `switch_tracker.db`: personal game and play-history data
- `history_data/`: optional raw API responses that may contain additional personal data
- `*.log`: runtime logs

These paths are covered by `.gitignore`. Before committing, it is still worth checking:

```bash
git status --short
git grep -nE 'session_token|access_token' -- ':!README.md' ':!README.zh-CN.md'
```

If a real token was ever committed, revoke the session through the Nintendo account first and then clean the Git history. Deleting only the latest copy does not invalidate an exposed credential.

## Development and testing

```bash
python -m pip install -r requirements-dev.txt
ruff check .
pytest
node --check script.js
node --test tests/frontend.test.cjs
```

Tests use temporary databases and do not read or modify real tokens or personal play data. Key files include:

- `get_switch_data.py`: authentication and data collection
- `tracker_db.py`: database schema, migrations, and idempotent persistence
- `server.py`: local dashboard and read-only JSON API
- `game_translation.py`: CSV translation workflow
- `daily_collect.py`: one-shot entry point for schedulers
- `templates/`, `script.js`, `styles.css`: dashboard frontend

## Roadmap

Near-term priorities include clearer authentication failure messages, data import and export, additional statistics, and automated frontend tests. The full, adjustable plan is in [ROADMAP.md](ROADMAP.md). It describes direction rather than promising fixed delivery dates.

## Contributing

Issues and focused improvements are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before getting started. Report security concerns privately according to [SECURITY.md](SECURITY.md), not through a public issue.

If you also maintain your own Switch play history, feedback about your workflow is especially useful. Bug reports, documentation fixes, and small, well-scoped improvements are all appreciated.

## Maintainer

Developed and maintained in spare time by [Chen Peng](https://github.com/pengchzn).

## License

The code is available under the [MIT License](LICENSE). Nintendo, Nintendo Switch, and related marks are trademarks of their respective owners. The MIT License does not grant rights to any third-party trademarks.
