# TraidSim auf Streamlit Community Cloud veroeffentlichen

## 1. GitHub vorbereiten

Dieses Projekt ist fuer Streamlit Cloud vorbereitet:

- `app.py` ist die Startdatei.
- `requirements.txt` enthaelt die Python-Pakete.
- `.streamlit/config.toml` startet die App im Dark Mode.
- `.streamlit/secrets.toml` bleibt lokal und wird nicht in GitHub hochgeladen.

## 2. Repository hochladen

Lade den Ordner `strategy_web_app_codex_handoff` in ein GitHub-Repository hoch.

Wichtig: Die Datei `.streamlit/secrets.toml` darf nicht ins Repository. Sie ist durch `.gitignore` ausgeschlossen.

## 3. Streamlit Cloud App erstellen

1. Oeffne https://streamlit.io/cloud
2. Mit GitHub anmelden.
3. `Create app` bzw. `Deploy app` auswaehlen.
4. Dein GitHub-Repository auswaehlen.
5. Main file path setzen:

```text
app.py
```

## 4. Secrets in Streamlit Cloud eintragen

In Streamlit Cloud unter `Advanced settings` den Inhalt deiner lokalen Datei `.streamlit/secrets.toml` in das Feld `Secrets` kopieren.

Aktuell lokal eingetragene Benutzer:

```toml
[auth.users]
admin = "73a467f5fbf2d4226e694d632e560f55e77de233a7d8a3140346789713d76f54"
juser-1 = "d4107f7b5ee04f3070bced8aaf99c29ca396615839e4fa6ebbc82512607427f7"
```

Die Klartext-Passwoerter dazu sind:

- `admin` / `Hyperopt-2026!`
- `juser-1` / `Juser-2026!`

## 5. Deploy starten

Nach dem Deploy bekommst du eine oeffentliche URL. Jeder mit dem Link sieht zuerst das Login-Fenster.

Hinweis: Streamlit Community Cloud ist fuer einfache Apps gut geeignet. Fuer produktive/private Nutzung mit staerkerer Zugriffskontrolle ist ein eigener Server oder ein Dienst wie Cloudflare Tunnel besser.
