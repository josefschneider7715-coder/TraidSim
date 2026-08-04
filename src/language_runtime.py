from __future__ import annotations


def inject_language_ui(source: str) -> str:
    """Erweitert die bestehende TraidSim-App ohne Änderung der Login-Logik."""
    import_marker = "from src.scored_signals import apply_scored_entry_signals\n"
    import_replacement = (
        "from src.scored_signals import apply_scored_entry_signals\n"
        "from src.i18n import LANGUAGES, translate\n"
    )
    if import_marker in source and "from src.i18n import LANGUAGES, translate" not in source:
        source = source.replace(import_marker, import_replacement, 1)

    exec_marker = 'exec(compile(_source, str(_legacy_path), "exec"), globals(), globals())'
    injected_exec = '''
_language_marker = "require_login()\\n\\nDISCLAIMER ="
_language_ui = """require_login()

_language_codes = list(LANGUAGES.keys())
_current_language = st.session_state.get(\"traidsim_language\", \"de\")
if _current_language not in _language_codes:
    _current_language = \"de\"
with st.sidebar:
    st.divider()
    _selected_language = st.selectbox(
        \"🌍 Sprache / Language / Язык\",
        options=_language_codes,
        index=_language_codes.index(_current_language),
        format_func=lambda code: LANGUAGES[code],
        key=\"traidsim_language_selector\",
    )
st.session_state[\"traidsim_language\"] = _selected_language
_t = lambda key: translate(key, _selected_language)

DISCLAIMER ="""
if _language_marker not in _source:
    raise RuntimeError(\"Einfügepunkt für die Sprachauswahl wurde nicht gefunden.\")
_source = _source.replace(_language_marker, _language_ui, 1)

_tab_marker = 'overview_tab, hyperopt_tab, telemetry_tab = st.tabs([\"Uebersicht\", \"Hyperopt\", \"Simulation\"])'
_tab_replacement = 'overview_tab, hyperopt_tab, telemetry_tab = st.tabs([_t(\"tab_overview\"), _t(\"tab_hyperopt\"), _t(\"tab_simulation\")])'
if _tab_marker not in _source:
    raise RuntimeError(\"Einfügepunkt für die übersetzten Hauptreiter wurde nicht gefunden.\")
_source = _source.replace(_tab_marker, _tab_replacement, 1)

exec(compile(_source, str(_legacy_path), \"exec\"), globals(), globals())
'''.strip()

    if exec_marker not in source:
        raise RuntimeError("Ausführungspunkt im TraidSim-Wrapper wurde nicht gefunden.")
    return source.replace(exec_marker, injected_exec, 1)
