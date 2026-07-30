from __future__ import annotations

from pathlib import Path

# Sofort-Hotfix: Die bewährte Hauptanwendung wird direkt ausgeführt.
# Dadurch bleiben Streamlit-Login, Session-State und secrets.toml exakt im
# ursprünglichen Ausführungskontext. Der vorherige Modul-Import-Hook konnte
# insbesondere bei st.stop()/st.rerun() die Anmeldung beeinträchtigen.
_legacy_path = Path(__file__).with_name("_legacy_app.py")
_source = _legacy_path.read_text(encoding="utf-8-sig")
exec(compile(_source, str(_legacy_path), "exec"), globals(), globals())
