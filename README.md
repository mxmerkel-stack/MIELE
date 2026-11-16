# Miele Dashboard

Fragt alle 15 Minuten die Miele-Third-Party-API ab (GitHub Action), speichert den Zustand in `docs/data/` und zeigt ihn unter `docs/index.html` (GitHub Pages) an.

## Einrichtung

1. Auf developer.miele.com Client-ID und Client-Secret holen.
2. Login-URL im Browser öffnen (`DEINE_ID` ersetzen), mit dem Miele-Konto anmelden:
   `https://auth.domestic.miele-iot.com/partner/realms/mcs/protocol/openid-connect/auth?client_id=DEINE_ID&response_type=code&redirect_uri=http://localhost&scope=openid`
3. Die Fehlerseite (localhost) ist normal. Aus der Adresszeile den Wert nach `code=` kopieren.
4. Lokal ausführen: `MIELE_CLIENT_ID=… MIELE_CLIENT_SECRET=… python scripts/login.py <code>`
5. Repo-Secrets anlegen: `MIELE_CLIENT_ID`, `MIELE_CLIENT_SECRET`, `MIELE_REFRESH_TOKEN`.
   Optional `GH_PAT` (Token mit Recht „Secrets: write" für dieses Repo), falls Miele das Refresh-Token rotiert.
6. Action „Miele abfragen" einmal manuell starten, dann in den Repo-Einstellungen GitHub Pages auf Branch `main`, Ordner `/docs` setzen.

## Hinweise

- Die API liefert nur den aktuellen Zustand. Die Historie entsteht durch die regelmäßige Abfrage.
- Die Statuswerte (`status_raw`) und Felder wie Energie/Wasser sind je Gerät verschieden. Nach dem ersten Lauf ein Blick in `docs/data/latest.json`, dann lassen sich die Karten und die Lauf-Erkennung im Dashboard anpassen.
- Alle Daten im Repo sind für jeden lesbar, solange das Repo öffentlich ist.
