"""Fragt alle Miele-Geräte ab und schreibt latest.json + history.jsonl nach docs/data/."""
import datetime as dt
import json
import os
import pathlib
import subprocess

from miele_common import api_get, refresh

DATA = pathlib.Path(__file__).resolve().parent.parent / "docs" / "data"
DATA.mkdir(parents=True, exist_ok=True)

client_id = os.environ["MIELE_CLIENT_ID"]
client_secret = os.environ["MIELE_CLIENT_SECRET"]
old_refresh = os.environ["MIELE_REFRESH_TOKEN"]

tok = refresh(client_id, client_secret, old_refresh)

# Falls Miele das Refresh-Token rotiert, neues Token als Secret zurückschreiben (braucht GH_PAT).
new_refresh = tok.get("refresh_token")
if new_refresh and new_refresh != old_refresh:
    if os.environ.get("GH_PAT") and os.environ.get("GITHUB_REPOSITORY"):
        subprocess.run(
            ["gh", "secret", "set", "MIELE_REFRESH_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
            input=new_refresh.encode(), check=True,
            env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]},
        )
    else:
        print("WARNUNG: Refresh-Token wurde rotiert, GH_PAT fehlt - Secret nicht aktualisiert.")


def val(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


devices = api_get("/devices?language=de", tok["access_token"])
now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

rows = []
for dev_id, d in devices.items():
    rem = val(d, "state", "remainingTime") or [0, 0]
    rows.append({
        "id": dev_id,
        "name": val(d, "ident", "deviceName") or val(d, "ident", "type", "value_localized") or dev_id,
        "type": val(d, "ident", "type", "value_localized"),
        "status": val(d, "state", "status", "value_localized"),
        "status_raw": val(d, "state", "status", "value_raw"),
        "program": val(d, "state", "ProgramID", "value_localized") or val(d, "state", "programType", "value_localized"),
        "phase": val(d, "state", "programPhase", "value_localized"),
        "remaining_min": rem[0] * 60 + rem[1] if len(rem) >= 2 else None,
        "energy_kwh": val(d, "state", "ecoFeedback", "currentEnergyConsumption", "value"),
        "water_l": val(d, "state", "ecoFeedback", "currentWaterConsumption", "value"),
    })

snapshot = {"ts": now, "devices": rows}
(DATA / "latest.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=1))
with open(DATA / "history.jsonl", "a") as f:
    f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

print(f"{len(rows)} Geräte gespeichert ({now})")
