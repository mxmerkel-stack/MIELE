"""Fragt alle Miele-Geräte ab, erkennt Programmläufe und schreibt nach docs/data/:

- latest.json      aktueller Zustand (nur bei Änderung oder stündlich neu geschrieben)
- raw_latest.json  ungefilterte API-Antwort (zum Prüfen, welche Felder das Gerät liefert)
- runs.json        alle erkannten Programmläufe mit Verbrauch, Temperatur, Schleuderzahl ...
"""
import datetime as dt
import json
import os
import pathlib
import subprocess

from miele_common import api_get, refresh

DATA = pathlib.Path(__file__).resolve().parent.parent / "docs" / "data"
DATA.mkdir(parents=True, exist_ok=True)

# Miele status_raw
ACTIVE = {5, 6, 9, 11}        # läuft, Pause, Programm unterbrochen, Spülstopp
FINISHED = {7}                # Programm beendet (Verbrauchswerte noch sichtbar)

client_id = os.environ["MIELE_CLIENT_ID"]
client_secret = os.environ["MIELE_CLIENT_SECRET"]
old_refresh = os.environ["MIELE_REFRESH_TOKEN"]

REPO = os.environ.get("GITHUB_REPOSITORY")
GH_ENV = {**os.environ, "GH_TOKEN": os.environ.get("GH_PAT", "")}


def fail(msg):
    print("::error::" + msg)
    raise SystemExit(1)


# Vor dem Token-Tausch prüfen, ob GH_PAT Secrets schreiben darf - sonst ginge das
# neue (rotierte) Miele-Token verloren und das alte wäre trotzdem verbraucht.
if REPO:
    if not os.environ.get("GH_PAT"):
        fail("Secret GH_PAT fehlt. Ohne GH_PAT kann das rotierte Miele-Token nicht gespeichert werden - Abbruch, Miele-Token bleibt gültig.")
    chk = subprocess.run(["gh", "api", f"repos/{REPO}/actions/secrets/public-key"],
                         capture_output=True, text=True, env=GH_ENV)
    if chk.returncode != 0:
        fail("GH_PAT darf keine Secrets schreiben (Token prüfen: Repo 'miele' ausgewählt, Berechtigung 'Secrets: Read and write', nicht abgelaufen). "
             "GitHub meldet: " + (chk.stderr or chk.stdout).strip()[:200] + " - Abbruch, Miele-Token bleibt gültig.")

tok = refresh(client_id, client_secret, old_refresh)

new_refresh = tok.get("refresh_token")
if new_refresh and new_refresh != old_refresh and REPO:
    res = subprocess.run(["gh", "secret", "set", "MIELE_REFRESH_TOKEN", "--repo", REPO],
                         input=new_refresh, capture_output=True, text=True, env=GH_ENV)
    if res.returncode != 0:
        fail("Neues Miele-Token konnte nicht gespeichert werden: " + (res.stderr or res.stdout).strip()[:200])
    print("Refresh-Token rotiert und Secret aktualisiert.")


def val(d, *keys):
    for k in keys:
        if isinstance(d, list):
            d = d[0] if d else None
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def num(x):
    """Miele liefert -32768 für 'kein Wert'."""
    if isinstance(x, (int, float)) and x not in (-32768, -32767):
        return x
    return None


def minutes(pair):
    if isinstance(pair, list) and len(pair) >= 2 and all(isinstance(v, int) for v in pair[:2]):
        return pair[0] * 60 + pair[1]
    return None


devices = api_get("/devices?language=de", tok["access_token"])
now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
now_s = now.isoformat()

(DATA / "raw_latest.json").write_text(json.dumps({"ts": now_s, "devices": devices}, ensure_ascii=False, indent=1))

rows = []
for dev_id, d in devices.items():
    st = d.get("state", {})
    temp = num(val(st, "targetTemperature", "value_raw"))
    rows.append({
        "id": dev_id,
        "name": val(d, "ident", "deviceName") or val(d, "ident", "type", "value_localized") or dev_id,
        "type": val(d, "ident", "type", "value_localized"),
        "model": val(d, "ident", "deviceIdentLabel", "techType"),
        "status": val(st, "status", "value_localized"),
        "status_raw": val(st, "status", "value_raw"),
        "program": val(st, "ProgramID", "value_localized") or val(st, "programType", "value_localized") or "",
        "program_raw": val(st, "ProgramID", "value_raw"),
        "phase": val(st, "programPhase", "value_localized") or "",
        "remaining_min": minutes(st.get("remainingTime")),
        "elapsed_min": minutes(st.get("elapsedTime")),
        "temp_c": temp / 100 if temp is not None else None,
        "spin_rpm": num(val(st, "spinningSpeed", "value_raw")),
        "energy_kwh": num(val(st, "ecoFeedback", "currentEnergyConsumption", "value")),
        "water_l": num(val(st, "ecoFeedback", "currentWaterConsumption", "value")),
        "energy_forecast": num(val(st, "ecoFeedback", "energyForecast")),
        "water_forecast": num(val(st, "ecoFeedback", "waterForecast")),
        "signal_info": val(st, "signalInfo"),
        "signal_failure": val(st, "signalFailure"),
        "signal_door": val(st, "signalDoor"),
    })

# --- latest.json nur bei Änderung (oder stündlich) schreiben, um Commits zu sparen ---
latest_path = DATA / "latest.json"
prev = json.loads(latest_path.read_text()) if latest_path.exists() else {}
changed = prev.get("devices") != rows
stale = True
if prev.get("ts"):
    stale = now - dt.datetime.fromisoformat(prev["ts"]) > dt.timedelta(minutes=55)
if changed or stale:
    latest_path.write_text(json.dumps({"ts": now_s, "devices": rows}, ensure_ascii=False, indent=1))

# --- Programmläufe erkennen ---
runs_path = DATA / "runs.json"
store = json.loads(runs_path.read_text()) if runs_path.exists() else {"open": {}, "runs": []}


def maxv(a, b):
    return b if a is None else (a if b is None else max(a, b))


for r in rows:
    o = store["open"].get(r["id"])
    active = r["status_raw"] in ACTIVE or (r["remaining_min"] or 0) > 0 and r["status_raw"] not in FINISHED
    finished = r["status_raw"] in FINISHED

    if active or (finished and o):
        if not o:
            start = now
            if r["elapsed_min"]:
                start = now - dt.timedelta(minutes=r["elapsed_min"])
            o = store["open"][r["id"]] = {
                "device_id": r["id"], "device": r["name"], "start": start.isoformat(),
                "program": r["program"], "program_raw": r["program_raw"],
            }
        o["program"] = r["program"] or o.get("program")
        o["temp_c"] = r["temp_c"] if r["temp_c"] is not None else o.get("temp_c")
        o["spin_rpm"] = r["spin_rpm"] if r["spin_rpm"] is not None else o.get("spin_rpm")
        o["energy_kwh"] = maxv(o.get("energy_kwh"), r["energy_kwh"])
        o["water_l"] = maxv(o.get("water_l"), r["water_l"])
        o["energy_forecast"] = o.get("energy_forecast") if o.get("energy_forecast") is not None else r["energy_forecast"]
        o["water_forecast"] = o.get("water_forecast") if o.get("water_forecast") is not None else r["water_forecast"]
        o["last_seen"] = now_s
        if r["elapsed_min"]:
            o["elapsed_min"] = r["elapsed_min"]

    if o and not active:
        o["end"] = now_s
        start = dt.datetime.fromisoformat(o["start"])
        o["duration_min"] = o.get("elapsed_min") or round((now - start).total_seconds() / 60)
        o.pop("last_seen", None)
        store["runs"].append(o)
        del store["open"][r["id"]]
        print(f"Lauf beendet: {o['device']} {o.get('program')} {o.get('energy_kwh')} kWh {o.get('water_l')} l")

store.pop("updated", None)
new_txt = json.dumps(store, ensure_ascii=False, indent=1)
if not runs_path.exists() or runs_path.read_text() != new_txt:
    runs_path.write_text(new_txt)

print(f"{len(rows)} Geräte geprüft ({now_s}), {len(store['runs'])} Läufe gespeichert")
