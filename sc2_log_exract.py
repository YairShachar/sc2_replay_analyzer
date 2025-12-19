import csv
import hashlib
import os
from datetime import timezone

import sc2reader
from sc2reader.events import tracker as tr

# ---------------- CONFIG ----------------

ME = "AppleJuice"  # <-- CHANGE IF NEEDED

WORKERS = {"SCV", "Drone", "Probe"}
TOWNHALLS = {
    "CommandCenter", "OrbitalCommand", "PlanetaryFortress",
    "Hatchery", "Lair", "Hive",
    "Nexus",
}

SNAPSHOTS = {
    "6m": 360,
    "8m": 480,
    "10m": 600,
}

# ---------------- UTILS ----------------

def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def safe_utc(dt):
    if not dt:
        return ""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.astimezone(timezone.utc).isoformat()

# ---------------- CORE EXTRACTION ----------------

def extract_units(replay):
    units = {}
    for e in replay.tracker_events:
        if isinstance(e, tr.UnitBornEvent):
            unit = e.unit
            name = getattr(unit, "name", None) or e.unit_type_name
            units[e.unit_id] = {
                "name": name,
                "born": int(e.second),
                "died": None,
                "pid": e.control_pid,
                "supply": getattr(unit, "supply", 0) or 0,
                "minerals": getattr(unit, "minerals", 0) or 0,
                "vespene": getattr(unit, "vespene", 0) or 0,
                "is_army": getattr(unit, "is_army", False),
            }
        elif isinstance(e, tr.UnitDiedEvent):
            if e.unit_id in units:
                units[e.unit_id]["died"] = int(e.second)
    return units

def alive_at(units, pid, names, t):
    return sum(
        1 for u in units.values()
        if u["pid"] == pid
        and u["name"] in names
        and u["born"] <= t
        and (u["died"] is None or u["died"] > t)
    )

def army_supply_at(units, pid, t):
    """Calculate total army supply for a player at a given time."""
    return sum(
        u["supply"] for u in units.values()
        if u["pid"] == pid
        and u["is_army"]
        and u["born"] <= t
        and (u["died"] is None or u["died"] > t)
    )

def army_value_at(units, pid, t):
    """Calculate total army value (minerals, gas) for a player at a given time."""
    minerals = gas = 0
    for u in units.values():
        if (u["pid"] == pid
            and u["is_army"]
            and u["born"] <= t
            and (u["died"] is None or u["died"] > t)):
            minerals += u["minerals"]
            gas += u["vespene"]
    return minerals, gas

def extract_row(replay_path):
    r = sc2reader.load_replay(replay_path, load_level=4)
    replay_id = sha1(replay_path)

    me = next(p for p in r.players if p.name == ME)
    opp = next(p for p in r.players if p.name != ME)

    units = extract_units(r)

    row = {
        "replay_id": replay_id,
        "played_at_utc": safe_utc(r.date),
        "map": r.map_name,
        "player_name": ME,
        "player_race": me.play_race,
        "opponent_race": opp.play_race,
        "result": me.result,
        "game_length_sec": int(r.length.total_seconds()),
    }

    # ---- Workers ----
    for k, t in SNAPSHOTS.items():
        row[f"workers_{k}"] = alive_at(units, me.pid, WORKERS, t)

    # ---- Bases ----
    row["bases_started_by_6m"] = alive_at(units, me.pid, TOWNHALLS, 360)
    row["bases_started_by_8m"] = alive_at(units, me.pid, TOWNHALLS, 480)

    townhall_times = sorted(
        u["born"] for u in units.values()
        if u["pid"] == me.pid and u["name"] in TOWNHALLS
    )
    row["natural_started_at"] = townhall_times[1] if len(townhall_times) > 1 else ""
    row["third_started_at"] = townhall_times[2] if len(townhall_times) > 2 else ""

    # ---- Army @ 8m ----
    if r.length.total_seconds() >= 480:
        row["army_supply_8m"] = army_supply_at(units, me.pid, 480)
        minerals_8m, gas_8m = army_value_at(units, me.pid, 480)
        row["army_minerals_8m"] = minerals_8m
        row["army_gas_8m"] = gas_8m
    else:
        row["army_supply_8m"] = ""
        row["army_minerals_8m"] = ""
        row["army_gas_8m"] = ""

    # ---- Worker kills / losses ----
    kills = losses = 0
    for e in r.tracker_events:
        if isinstance(e, tr.UnitDiedEvent) and e.second <= 480:
            unit_name = e.unit.name if e.unit else None
            if unit_name in WORKERS:
                if e.killer_pid == me.pid:
                    kills += 1
                elif e.killer_pid == opp.pid:
                    losses += 1

    row["worker_kills_0_8m"] = kills
    row["worker_losses_0_8m"] = losses

    # ---- First attack (very rough heuristic) ----
    first_attack = next(
        (int(e.second) for e in r.tracker_events
         if isinstance(e, tr.UnitDiedEvent)
         and e.killer_pid == me.pid),
        ""
    )
    row["first_attack_time"] = first_attack

    # ---- Supply blocks & unspent (BEST-EFFORT PLACEHOLDERS) ----
    row["supply_blocks_count"] = ""
    row["longest_supply_block_sec"] = ""
    row["unspent_6m"] = ""
    row["unspent_8m"] = ""
    row["unspent_10m"] = ""

    # ---- Manual fields ----
    for k in [
        "opener_label",
        "planned_win_condition",
        "scouted_opponent_plan",
        "turning_point",
        "biggest_mistake",
        "one_fix_next_game",
        "drill_to_practice",
    ]:
        row[k] = ""

    return row

# ---------------- CSV ----------------

def append_csv(out, row):
    exists = os.path.exists(out)
    with open(out, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not exists:
            writer.writeheader()
        writer.writerow(row)

# ---------------- CLI ----------------

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("--out", default="sc2_log_v2.csv")
    args = ap.parse_args()

    row = extract_row(args.replay)
    append_csv(args.out, row)
    print("✔ Appended:", args.out)