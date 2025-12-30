# SC2 Replay Analyzer

Analyze your StarCraft II replays with filtering, stats, and beautiful terminal output.

## Features

- **Auto-detect** SC2 replay folders on Mac, Windows, and Linux
- **Parse replays** and extract worker counts, army value, APM, MMR, and more
- **Interactive filtering** - dynamically filter by matchup, result, length, workers
- **Auto-completion** - tab-complete commands with usage hints
- **Win/loss streaks** - find patterns in your games
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

The `sc2 live` command opens an interactive filtering mode with tab-completion:

```
SC2 Replay Analyzer - Interactive Mode
Type commands to filter. 'help' for options, 'q' to quit. Tab for completion.

> -m TvZ          # Filter by matchup
> -r W            # Show only wins
> -l >10:00       # Games longer than 10 minutes
> -w <40          # Games with <40 workers at 8min
> -s win:3+       # Find 3+ win streaks
> +p 1            # Add 1 previous game (cumulative)
> clear           # Reset all filters
> q               # Quit
```

### Filter Commands

<!-- AUTO-GENERATED: FILTER_COMMANDS -->
| Command | Description | Example |
|---------|-------------|---------|
| `-n, --limit` | Limit results to N games | `-n 50` |
| `-m, --matchup` | Filter by matchup (TvZ, TvP, etc) | `-m TvZ` |
| `-r, --result` | Filter by result (W/L) | `-r W` |
| `-l, --length` | Filter by game length | `-l >8:00` |
| `-w, --workers` | Filter by workers @8m | `-w <40` |
| `-d, --days` | Games from last N days | `-d 7` |
| `-s, --streaks` | Find win/loss streaks | `-s win:3+` |
| `--map` | Filter by map name | `--map Alcyone` |
| `+p, --prev` | Add N previous games (cumulative) | `+p 1` |
| `+n, --next` | Add N next games (cumulative) | `+n 2` |
| `columns` | Manage display columns | |
| `clear` | Reset all filters | |
| `help` | Show help | |
| `q` | Quit | |
<!-- END AUTO-GENERATED -->

### Column Commands

| Command | Description | Example |
|---------|-------------|---------|
| `columns` | List available columns | |
| `columns add <col>` | Add column(s) to display | `columns add bases_6m` |
| `columns remove <col>` | Remove column(s) | `columns remove mmr` |
| `columns reset` | Reset to default columns | |

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

<!-- AUTO-GENERATED: AVAILABLE_COLUMNS -->
`apm`, `army`, `bases_10m`, `bases_6m`, `bases_8m`, `date`, `length`, `map`, `matchup`, `mmr`, `opponent`, `opponent_apm`, `opponent_mmr`, `result`, `worker_kills`, `worker_losses`, `workers_10m`, `workers_6m`, `workers_8m`
<!-- END AUTO-GENERATED -->

## Development

### Updating README

After modifying commands, run:

```bash
python scripts/generate_readme.py
```

This updates the auto-generated sections marked with `<!-- AUTO-GENERATED -->` comments.

## Requirements

- Python 3.8+
- StarCraft II replays (.SC2Replay files)

## License

MIT
