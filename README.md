# SC2 Replay Analyzer

Analyze your StarCraft II replays with filtering, stats, and beautiful terminal output.

## Features

- **Auto-detect** SC2 replay folders on Mac, Windows, and Linux
- **Parse replays** and extract worker counts, army value, APM, MMR, and more
- **Interactive filtering** - dynamically filter by matchup, result, length, workers
- **Win/loss statistics** with averages and matchup breakdowns
- **SQLite caching** - parse each replay only once

## Installation

```bash
pip install sc2-replay-analyzer
```

## Quick Start

```bash
# First run - auto-detects your replay folder and player name
sc2

# Scan for new replays
sc2 scan

# Interactive filtering mode
sc2 live

# Show statistics
sc2 stats
```

## Commands

| Command | Description |
|---------|-------------|
| `sc2` | First run: setup wizard. After: auto-scan + interactive mode |
| `sc2 scan` | Scan replay folder for new games |
| `sc2 live` | Interactive filtering mode |
| `sc2 stats` | Show aggregate statistics |
| `sc2 config` | Re-run setup / change player name |
| `sc2 show` | Show games with filters |
| `sc2 export` | Export to CSV |
| `sc2 latest` | Show detailed stats for most recent game |

## Interactive Mode

The `sc2 live` command opens an interactive filtering mode:

```
SC2 Replay Analyzer - Interactive Mode
Type commands to filter. 'help' for options, 'q' to quit.

> -m TvZ          # Filter by matchup
> -r W            # Show only wins
> -l >10:00       # Games longer than 10 minutes
> -w <40          # Games with <40 workers at 8min
> clear           # Reset all filters
> q               # Quit
```

### Filter Commands

| Command | Description | Example |
|---------|-------------|---------|
| `-n <num>` | Limit to N games | `-n 50` |
| `-m <matchup>` | Filter by matchup | `-m TvZ` |
| `-r <result>` | Filter by result | `-r W`, `-r L` |
| `-l <op><time>` | Filter by length | `-l >=8:00`, `-l <5:00` |
| `-w <op><num>` | Filter by workers @8m | `-w <=40`, `-w >50` |
| `--map <name>` | Filter by map name | `--map Pylon` |
| `-d <days>` | Games from last N days | `-d 7` |
| `clear` | Reset all filters | |
| `help` | Show help | |
| `q` | Quit | |

## Configuration

Config is stored in `~/.sc2analyzer/config.toml`:

```toml
player_name = "YourName"
replay_folder = "~/Library/Application Support/Blizzard/StarCraft II/Accounts/.../Replays/Multiplayer"

[benchmarks]
workers_6m = 40
workers_8m = 55

[display]
columns = ["date", "map", "matchup", "result", "mmr", "apm", "workers_8m", "army", "length"]
```

### Available Columns

`date`, `map`, `matchup`, `result`, `mmr`, `opponent_mmr`, `apm`, `opponent_apm`, `workers_6m`, `workers_8m`, `workers_10m`, `army`, `length`, `bases_6m`, `bases_8m`, `worker_kills`, `worker_losses`

## Requirements

- Python 3.8+
- StarCraft II replays (.SC2Replay files)

## License

MIT
