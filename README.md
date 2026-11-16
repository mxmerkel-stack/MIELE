# Miele Dashboard

Fragt alle 15 Minuten die Miele-Third-Party-API ab (GitHub Action „Miele abfragen"), speichert den Zustand in `docs/data/` und zeigt ihn unter `docs/index.html` (GitHub Pages) an.

## Einrichtung

1. Auf developer.miele.com Client-ID und Client-Secret holen.
2. Repo-Secrets anlegen: `MIELE_CLIENT_ID`, `MIELE_CLIENT_SECRET`.
3. Auf dem Mac im Terminal:
   ```
   git clone https://github.com/mxmerkel-stack/miele ~/miele
   cd ~/miele
   python3 scripts/login.py
   ```
   Client-ID und Secret eingeben, im geöffneten Browser bei Miele anmelden.
   Das Refresh-Token landet in der Zwischenablage.
4. Repo-Secret `MIELE_REFRESH_TOKEN` anlegen (Cmd+V).
5. Action „Miele abfragen" manuell starten, dann unter Settings → Pages Branch `main`, Ordner `/docs` wählen.

Optional `GH_PAT` (Token mit „Secrets: write" für dieses Repo), falls Miele das Refresh-Token rotiert.

## Hinweise

- Die API liefert nur den aktuellen Zustand. Die Historie entsteht durch die regelmäßige Abfrage.
- Solange das Repo öffentlich ist, sind die Daten in `docs/data/` für jeden lesbar.
