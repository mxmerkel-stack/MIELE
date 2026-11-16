"""Einmaliges Login bei Miele: holt ein Refresh-Token.

Lokal (empfohlen):   python3 scripts/login.py
  Fragt Client-ID und Client-Secret ab, öffnet den Browser zum Miele-Login,
  fängt den Code automatisch ab, tauscht ihn sofort und legt das
  Refresh-Token in die Zwischenablage.

In Actions (Workflow "Miele Login"): liest alles aus Umgebungsvariablen und
speichert das Token direkt als Secret MIELE_REFRESH_TOKEN (braucht GH_PAT).
"""
import getpass
import http.server
import os
import socket
import subprocess
import sys
import urllib.parse
import webbrowser

from miele_common import AUTH_URL, REDIRECT_URI, exchange_code

IN_ACTIONS = bool(os.environ.get("GITHUB_ACTIONS"))


def ask(prompt, env, secret=False):
    val = os.environ.get(env, "").strip()
    if val:
        return val
    if IN_ACTIONS:
        print(f"::error::Umgebungsvariable {env} fehlt (Secret/Eingabe leer?)")
        raise SystemExit(1)
    val = (getpass.getpass if secret else input)(prompt).strip()
    if not val:
        raise SystemExit(f"Leere Eingabe für: {prompt.strip()}")
    return val


def catch_code(client_id):
    """Startet einen Mini-Server auf localhost:80, öffnet den Login und wartet auf den Code."""
    received = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q:
                received["code"] = q["code"][0]
                msg = "Fertig. Du kannst dieses Fenster schließen und zum Terminal zurückkehren."
            elif "error" in q:
                received["error"] = q.get("error_description", q["error"])[0]
                msg = "Fehler beim Miele-Login: " + received["error"]
            else:
                msg = "Warte auf Miele-Login ..."
            body = f"<html><meta charset='utf-8'><body style='font:18px sans-serif;padding:40px'>{msg}</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *a):
            pass

    class DualStackServer(http.server.HTTPServer):
        address_family = socket.AF_INET6

        def server_bind(self):
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            super().server_bind()

    try:
        server = DualStackServer(("::", 80), Handler)
    except OSError:
        try:
            server = http.server.HTTPServer(("", 80), Handler)
        except OSError as e:
            print(f"Konnte localhost:80 nicht öffnen ({e}). Bitte den Code manuell eingeben.")
            return None

    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code",
        "redirect_uri": REDIRECT_URI, "state": "miele",
    })
    print("Browser öffnet sich jetzt. Bitte bei Miele anmelden ...")
    webbrowser.open(url)
    server.timeout = 300
    while "code" not in received and "error" not in received:
        server.handle_request()
    server.server_close()
    if "error" in received:
        raise SystemExit("Miele-Login abgelehnt: " + received["error"])
    return received["code"]


client_id = ask("Client-ID: ", "MIELE_CLIENT_ID")
client_secret = ask("Client-Secret (bleibt unsichtbar): ", "MIELE_CLIENT_SECRET", secret=True)

if len(sys.argv) > 1:
    code = sys.argv[1]
elif IN_ACTIONS or os.environ.get("MIELE_CODE"):
    code = ask("Code: ", "MIELE_CODE")
else:
    code = catch_code(client_id) or ask("Code: ", "MIELE_CODE")

lengths = f"Längen: Client-ID {len(client_id)}, Secret {len(client_secret)}, Code {len(code)}"
print(("::notice::" if IN_ACTIONS else "") + lengths)
tok = exchange_code(client_id, client_secret, code)
refresh_token = tok["refresh_token"]

if IN_ACTIONS:
    if not os.environ.get("GH_PAT"):
        print("::error::GH_PAT fehlt - Token kann nicht als Secret gespeichert werden")
        raise SystemExit(1)
    subprocess.run(
        ["gh", "secret", "set", "MIELE_REFRESH_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
        input=refresh_token.encode(), check=True,
        env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]},
    )
    print("::notice::Refresh-Token wurde als Secret MIELE_REFRESH_TOKEN gespeichert.")
else:
    try:
        subprocess.run(["pbcopy"], input=refresh_token.encode(), check=True)
        print("\nERFOLG: Das Refresh-Token liegt jetzt in deiner Zwischenablage.")
        print("Jetzt auf GitHub als Secret MIELE_REFRESH_TOKEN einfügen (Cmd+V).")
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\nRefresh-Token (als Secret MIELE_REFRESH_TOKEN speichern):")
        print(refresh_token)
