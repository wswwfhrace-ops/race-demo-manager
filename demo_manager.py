# =============================================================================
# demo_manager.py
# Warfork (+ Warsow-ready) personal best demo tracker
# =============================================================================


# -----------------------------------------------------------------------------
# imports
# -----------------------------------------------------------------------------

import gzip
import json
import platform
import re
from datetime import datetime
from pathlib import Path
from shutil import move
from time import sleep


# -----------------------------------------------------------------------------
# constants
# -----------------------------------------------------------------------------

BASE_DIR            = Path(__file__).parent
CONFIG_FILE         = BASE_DIR / "config.json"
WARFORK_RECORDS     = BASE_DIR / "records_wf.json"
WARSOW_RECORDS      = BASE_DIR / "records_wsw.json"
RECORDS_ALL = BASE_DIR / "records_all.json"
DEMO_MANAGER_DIR    = "demo_manager"
POLL_INTERVAL       = 1.0   # seconds between watcher polls


# -----------------------------------------------------------------------------
# config
# -----------------------------------------------------------------------------

_config_cache = None


def load_config():
    """Load config from disk. Cached after first load so helpers can call
    this freely without reading the file repeatedly."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    if not CONFIG_FILE.exists():
        _config_cache = _run_first_time_setup()
    else:
        with open(CONFIG_FILE, "r") as f:
            _config_cache = json.load(f)
    return _config_cache


def _save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def _run_first_time_setup():
    """Interactive first-time setup. Returns the saved config dict."""

    print("=" * 50)
    print("Demo Manager - First Time Setup")
    print("=" * 50)
    print()

    player_name = input("Enter your player name: ").strip()
    print()

    print("Binds and aliases will be written to demo_manager.cfg")
    print("and loaded via autoexec.cfg. Existing settings are kept.")
    print("Press ENTER to use the default.")
    print()

    restart_key = input("Restart race key  [mouse4]: ").strip() or "mouse4"
    noclip_key  = input("Noclip key toggle [mouse3]: ").strip() or "mouse3"
    print()

    warfork_folder = _ask_folder("Warfork", _default_warfork_path())
    warsow_folder  = _ask_folder("Warsow",  _default_warsow_path())

    config = {
        "player_name":          player_name,
        "warfork_demos_folder": warfork_folder,
        "warsow_demos_folder":  warsow_folder,
        "restart_key":          restart_key,
        "noclip_key":           noclip_key,
    }

    _save_config(config)
    _create_game_folders(config)

    if warfork_folder:
        _install_demo_manager_cfg(
            Path(warfork_folder).parent / "demo_manager.cfg",
            restart_key,
            noclip_key,
        )
        _install_autoexec_hook(
            Path(warfork_folder).parent / "autoexec.cfg"
        )

    if warsow_folder:
        _install_demo_manager_cfg(
            Path(warsow_folder).parent / "demo_manager.cfg",
            restart_key,
            noclip_key,
        )
        _install_autoexec_hook(
            Path(warsow_folder).parent / "autoexec.cfg"
        )

    print()
    print("Setup complete!")
    print()

    if warfork_folder:
        print("To import old Warfork PB demos, copy them into:")
        print(f"  {get_unprocessed_folder('warfork')}")
        print()

    if warsow_folder:
        print("To import old Warsow PB demos, copy them into:")
        print(f"  {get_unprocessed_folder('warsow')}")
        print()

    input("Press ENTER when ready...")
    print()

    return config


def _ask_folder(game_name, default_path):
    """Prompt the user for a demos folder. Returns '' if they type NIL."""

    print(f"{game_name} demos folder")
    print(f"  Default: {default_path}")
    print("  Press ENTER to use the default.")
    print("  Type a path to use a different folder.")
    print("  Type NIL if you do not play this game.")
    print()

    response = input("> ").strip()
    print()

    if response.lower() == "nil":
        return ""

    if response == "":
        folder = str(default_path)
    else:
        folder = str(Path(response).expanduser())

    if not Path(folder).exists():
        print(f"  WARNING: Path does not exist: {folder}")
        print()

    return folder


def _default_warfork_path():
    """Return the default Warfork demos path for this OS."""

    home = Path.home()

    if platform.system() == "Windows":
        return (
            home
            / "Documents"
            / "My Games"
            / "Warfork 2.1"
            / "racemod_2.1"
            / "demos"
        )

    return (
        home
        / ".local"
        / "share"
        / "warfork-2.1"
        / "racemod_2.1"
        / "demos"
    )


def _default_warsow_path():
    """Return the most likely Warsow demos path for this OS."""

    home = Path.home()

    if platform.system() == "Windows":
        return home / "AppData" / "Roaming" / "Warsow 2.1" / "racemod_2.1" / "demos"

    return home / ".local" / "share" / "warsow-2.1" / "racemod_2.1" / "demos"


# -----------------------------------------------------------------------------
# path helpers
# -----------------------------------------------------------------------------
# Generic per-game helpers. Use game="warfork" or game="warsow".
# All call load_config() internally — no config parameter needed at call sites.

def get_manager_folder(game):
    config = load_config()
    if game == "warfork":
        base = config["warfork_demos_folder"]
    else:
        base = config["warsow_demos_folder"]
    return Path(base) / DEMO_MANAGER_DIR


def get_archive_folder(game):
    return get_manager_folder(game) / "demos"


def get_unprocessed_folder(game):
    return get_manager_folder(game) / "unprocessed demos"


def get_invalid_folder(game):
    return get_manager_folder(game) / "invalid demos"


def _create_game_folders(config):
    """Create the demo manager folder structure for every enabled game."""
    for game, key in (("warfork", "warfork_demos_folder"),
                      ("warsow",  "warsow_demos_folder")):

        base = config[key]
        if not base:
            continue

        manager = Path(base) / DEMO_MANAGER_DIR

        for path in (
                manager / "demos",
                manager / "unprocessed demos",
                manager / "invalid demos",
        ):
            path.mkdir(parents=True, exist_ok=True)


# -----------------------------------------------------------------------------
# demo parsing
# -----------------------------------------------------------------------------

# The "End:" line contains the definitive finish time.
# Format inside the binary file:  ^8End: ^700:26.092 ...
_END_PATTERN = re.compile(r"\^8End:\s*\^\d(\d{2}:\d{2}\.\d{3})")

# mapname is stored as:  mapname\x00<name>\x00gametype
_MAPNAME_PATTERN = re.compile(r"mapname\x00([^\x00]+)\x00gametype")




def _read_demo(path):
    """Read Warfork or Warsow demo as latin-1 text."""
    suffix = Path(path).suffix.lower()

    if suffix.startswith(".wdz"):
        with gzip.open(path, "rb") as f:
            return f.read().decode("latin-1", errors="ignore")

    return Path(path).read_bytes().decode("latin-1", errors="ignore")


def _get_map_name(text):
    m = _MAPNAME_PATTERN.search(text)
    return m.group(1) if m else None


def _get_time(text):
    """Extract the finish time. Use the last match — the demo repeats the
    finish block multiple times, the last one is the cleanest."""
    matches = _END_PATTERN.findall(text)
    return matches[-1] if matches else None




def _time_to_ms(time_str):
    """Convert '00:26.092' to milliseconds (26092)."""
    mins, rest = time_str.split(":")
    secs, millis = rest.split(".")
    return int(mins) * 60000 + int(secs) * 1000 + int(millis)


def get_demo_type(path):
    """Return 'warfork', 'warsow', or None based on file extension."""
    suffix = Path(path).suffix.lower()
    if suffix.startswith(".wfdz"):
        return "warfork"
    if suffix.startswith(".wdz"):
        return "warsow"
    return None


def parse_demo(path):
    """Parse a demo file. Returns a result dict or None if run was not finished.

    Result keys:
        map      : str  e.g. 'inder-bless3'
        time_str : str  e.g. '00:26.092'
        time_ms  : int  e.g. 26092
    """
    text = _read_demo(path)

    map_name = _get_map_name(text)
    if map_name is None:
        return None

    time_str = _get_time(text)

    if time_str is None:
        return None

    return {
        "map":      map_name,
        "time_str": time_str,
        "time_ms":  _time_to_ms(time_str),
    }


# -----------------------------------------------------------------------------
# records
# -----------------------------------------------------------------------------

def load_records(game):
    path = WARFORK_RECORDS if game == "warfork" else WARSOW_RECORDS
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return json.load(f)


def save_records(game, records):
    path = WARFORK_RECORDS if game == "warfork" else WARSOW_RECORDS

    with open(path, "w") as f:
        json.dump(records, f, indent=4)

    rebuild_combined_records()

def rebuild_combined_records():
    """Generate records_all.json containing the best run per map."""

    combined = {}

    for game, path in (
        ("warfork", WARFORK_RECORDS),
        ("warsow", WARSOW_RECORDS),
    ):

        if not path.exists():
            continue

        with open(path, "r") as f:
            records = json.load(f)

        for map_name, data in records.items():

            existing = combined.get(map_name)

            if existing is None or data["time_ms"] < existing["time_ms"]:
                combined[map_name] = {
                    **data,
                    "game": game,
                }

    with open(RECORDS_ALL, "w") as f:
        json.dump(combined, f, indent=4)


def is_pb(records, result):
    """Return True if result is a new personal best for its map."""
    map_name = result["map"]

    if map_name not in records:
        return True

    return result["time_ms"] <= records[map_name]["time_ms"]


def update_record(records, result, archived_name):
    records[result["map"]] = {
        "time_ms":   result["time_ms"],
        "time_str":  result["time_str"],
        "demo_file": archived_name,
    }


# -----------------------------------------------------------------------------
# cfg installation
# -----------------------------------------------------------------------------

_DEMO_MANAGER_CFG = """\
set dslot_cmd "demo_slot_0"

alias demo_slot_0 "stop; join; record run_00; set dslot_cmd demo_slot_1; echo ^2[wf-demos]^7 recording run_00"
alias demo_slot_1 "stop; join; record run_01; set dslot_cmd demo_slot_2; echo ^2[wf-demos]^7 recording run_01"
alias demo_slot_2 "stop; join; record run_02; set dslot_cmd demo_slot_3; echo ^2[wf-demos]^7 recording run_02"
alias demo_slot_3 "stop; join; record run_03; set dslot_cmd demo_slot_4; echo ^2[wf-demos]^7 recording run_03"
alias demo_slot_4 "stop; join; record run_04; set dslot_cmd demo_slot_5; echo ^2[wf-demos]^7 recording run_04"
alias demo_slot_5 "stop; join; record run_05; set dslot_cmd demo_slot_6; echo ^2[wf-demos]^7 recording run_05"
alias demo_slot_6 "stop; join; record run_06; set dslot_cmd demo_slot_7; echo ^2[wf-demos]^7 recording run_06"
alias demo_slot_7 "stop; join; record run_07; set dslot_cmd demo_slot_8; echo ^2[wf-demos]^7 recording run_07"
alias demo_slot_8 "stop; join; record run_08; set dslot_cmd demo_slot_9; echo ^2[wf-demos]^7 recording run_08"
alias demo_slot_9 "stop; join; record run_09; set dslot_cmd demo_slot_0; echo ^2[wf-demos]^7 recording run_09"

alias pm_stop "stop; noclip"

bind {restart_key} "vstr dslot_cmd"
bind {noclip_key} "pm_stop"
"""


def _install_demo_manager_cfg(cfg_path, restart_key, noclip_key):
    contents = _DEMO_MANAGER_CFG.format(
        restart_key=restart_key,
        noclip_key=noclip_key,
    )
    cfg_path.write_text(contents, encoding="utf-8")
    print(f"  Created: {cfg_path}")


def _install_autoexec_hook(autoexec_path):
    """Ensure 'exec demo_manager.cfg' is the final line in autoexec.cfg.
    If it already exists anywhere in the file it is removed and re-added at
    the end, so other cfgs cannot overwrite the binds by loading after it."""

    line = "exec demo_manager.cfg"
    lines = []

    if autoexec_path.exists():
        text = autoexec_path.read_text(encoding="utf-8", errors="ignore")
        # Remove any existing occurrence (exact line match) so we can
        # re-add it at the end — guarantees it loads last and wins
        lines = [l for l in text.splitlines() if l.strip() != line]

    # Strip trailing blank lines then append our line cleanly
    while lines and lines[-1].strip() == "":
        lines.pop()

    lines.append("")
    lines.append(line)

    autoexec_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Updated: {autoexec_path}")


# -----------------------------------------------------------------------------
# archiving
# -----------------------------------------------------------------------------

def _archive_demo(source_path, result, player_name, game):
    """Move a PB demo to the archive folder with a descriptive filename.
    Returns the new filename string."""

    date_str  = datetime.fromtimestamp(source_path.stat().st_mtime).strftime("%d-%m-%Y")
    safe_time = result["time_str"].replace(":", ".")
    tag       = "WF" if game == "warfork" else "WSW"

    new_name = (
        f'{result["map"]} '
        f'[{safe_time}] '
        f'{tag} '
        f'by {player_name} '
        f'{date_str}'
        f'{source_path.suffix}'
    )

    destination = get_archive_folder(game) / new_name

    # If a file with this name already exists, add a counter suffix
    # to avoid silently overwriting an existing archived demo
    counter = 1
    while destination.exists():
        dupe_name = (
            f'{result["map"]} '
            f'[{safe_time}] '
            f'{tag} '
            f'by {player_name} '
            f'{date_str} '
            f'({counter})'
            f'{source_path.suffix}'
        )
        destination = get_archive_folder(game) / dupe_name
        counter += 1

    move(source_path, destination)

    return destination.name


# -----------------------------------------------------------------------------
# importing
# -----------------------------------------------------------------------------

def import_old_demos(game):
    """Process any demos sitting in the unprocessed folder."""
    processed = 0
    pbs = 0
    invalid = 0

    config = load_config()

    folder_key = f"{game}_demos_folder"
    if not config.get(folder_key):
        return

    pattern    = "*.wfdz*" if game == "warfork" else "*.wdz*"
    demo_files = list(get_unprocessed_folder(game).glob(pattern))

    if not demo_files:
        return

    print()
    print(f"Found {len(demo_files)} unprocessed {game} demo(s).")
    choice = input("Import them now? (Y/N): ").strip().lower()

    if choice != "y":
        return

    records = load_records(game)

    for demo in demo_files:
        processed += 1

        print(f"  {demo.name}")
        result = parse_demo(demo)

        if result is None:
            invalid += 1
            move(demo, get_invalid_folder(game) / demo.name)
            print("    Skipped - not a completed run")
            continue

        archived_name = _archive_demo(
            demo,
            result,
            config["player_name"],
            game,
        )

        if is_pb(records, result):
            pbs += 1
            update_record(records, result, archived_name)
            print(f"    NEW PB!  {result['time_str']}  {result['map']}")
        else:
            print(f"    Not a PB  ({result['time_str']}  {result['map']})")

    save_records(game, records)
    print("Import complete")
    print(f"Processed: {processed}")
    print(f"PBs found: {pbs}")
    print(f"Invalid: {invalid}")
    print()
    print()


# -----------------------------------------------------------------------------
# watcher
# -----------------------------------------------------------------------------

def _get_run_files(folder):
    """Return all run_XX demo files found in folder, sorted."""
    files = []

    for i in range(10):
        files.extend(folder.glob(f"run_{i:02d}.wfdz*"))
        files.extend(folder.glob(f"run_{i:02d}.wdz*"))

    return sorted(files)


def _wait_for_file_to_settle(path):
    """Block until the file size stops changing between checks.
    Protects against reading a file the game is still writing to."""
    while True:

        try:
            size_before = path.stat().st_size
        except FileNotFoundError:
            return

        sleep(0.5)

        try:
            size_after = path.stat().st_size
        except FileNotFoundError:
            return

        if size_before == size_after:
            return


def _process_live_demo(path):
    """Parse a completed run file and save it if it is a PB."""

    if not path.exists():
        return

    print()
    print(f"  Checking {path.name}")

    # Wait for the game to finish writing before we read
    _wait_for_file_to_settle(path)

    game = get_demo_type(path)
    if game is None:
        print("  Unknown file type - skipped")
        return

    result = parse_demo(path)

    if result is None:
        print("  Not a completed run")
        return

    print(f"  Map:  {result['map']}")
    print(f"  Time: {result['time_str']}")

    records = load_records(game)
    config  = load_config()

    if not is_pb(records, result):
        prev = records[result["map"]]["time_str"]
        print(f"  Not a PB  (best: {prev})")
        return

    if result["map"] in records:
        prev = records[result["map"]]["time_str"]
        prev_ms = records[result["map"]]["time_ms"]

        if result["time_ms"] < prev_ms:
            improvement = (prev_ms - result["time_ms"]) / 1000
            print(f"  Previous PB: {prev}")
            print(f"  Improvement: -{improvement:.3f}s")
        else:
            print(f"  Tied PB: {prev}")

    archived_name = _archive_demo(
        path,
        result,
        config["player_name"],
        game,
    )

    update_record(records, result, archived_name)
    save_records(game, records)

    print("  *** NEW PB! ***")
    print(f"  Saved as: {archived_name}")
    print()


def watch_runs():
    """Poll the Warfork demos folder for run slot changes.

    The key insight: when run_06 starts recording, run_05 is definitely
    finished. We use that slot-rotation signal rather than a timer, which
    is more reliable than guessing whether the game is still writing.
    """

    config = load_config()

    watch_folders = []

    if config.get("warfork_demos_folder"):
        watch_folders.append(Path(config["warfork_demos_folder"]))

    if config.get("warsow_demos_folder"):
        watch_folders.append(Path(config["warsow_demos_folder"]))

    if not watch_folders:
        print("No demo folders configured.")
        return



    # Snapshot current mtimes so we only react to new changes
    known_state = {}

    for folder in watch_folders:
        for f in _get_run_files(folder):
            if f.exists():
                known_state[str(f)] = f.stat().st_mtime

    last_run_file = {
        "warfork": None,
        "warsow": None,
    }

    print("Watching folders:")

    for folder in watch_folders:
        print(f"  {folder}")

    print()
    print("Waiting for runs... (Ctrl+C to stop)")
    print()

    try:
        while True:

            for folder in watch_folders:
                for file in _get_run_files(folder):

                    if not file.exists():
                        continue

                    current_mtime = file.stat().st_mtime
                    old_mtime     = known_state.get(str(file))

                    if current_mtime == old_mtime:
                        continue

                    # File changed — update our snapshot
                    known_state[str(file)] = current_mtime

                    game = get_demo_type(file)

                    if last_run_file[game] is None or last_run_file[game] == file:
                        last_run_file[game] = file
                        continue

                    print(f"[{game}] New run:  {file.name}")
                    print(f"[{game}] Previous: {last_run_file[game].name}")

                    try:
                        _process_live_demo(last_run_file[game])
                    except Exception as e:
                        print(f"  Error processing demo: {e}")

                    last_run_file[game] = file

            sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print()
        print("Stopped.")


# -----------------------------------------------------------------------------
# main
# -----------------------------------------------------------------------------



if __name__ == "__main__":

    load_config()

    rebuild_combined_records()

    import_old_demos("warfork")
    import_old_demos("warsow")  # uncomment when Warsow support is ready

    print("Ready.")
    print()

    watch_runs()

