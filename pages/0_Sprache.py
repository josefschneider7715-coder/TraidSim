from __future__ import annotations

import streamlit as st

from src.i18n import LANGUAGES, translate


st.set_page_config(page_title="TraidSim – Sprache", page_icon="🌍", layout="wide")

current_language = st.session_state.get("traidsim_language", "de")
language_codes = list(LANGUAGES.keys())
current_index = language_codes.index(current_language) if current_language in language_codes else 0

selected_language = st.selectbox(
    "🌍 Sprache / Language / Язык",
    options=language_codes,
    index=current_index,
    format_func=lambda code: LANGUAGES[code],
    key="traidsim_language_selector_page",
)
st.session_state["traidsim_language"] = selected_language

t = lambda key: translate(key, selected_language)

st.title(f"🌍 {t('language')}")

if selected_language == "de":
    st.success("Deutsch wurde für diese TraidSim-Sitzung ausgewählt.")
    st.write(
        "Die Sprachauswahl wird bereits von den neuen Dokumentations- und Hyperopt-2-Bereichen verwendet. "
        "Die bestehende Hauptanwendung wird schrittweise auf zentrale Übersetzungsschlüssel umgestellt."
    )
elif selected_language == "en":
    st.success("English has been selected for this TraidSim session.")
    st.write(
        "The language selection is already used by the new documentation and Hyperopt 2 areas. "
        "The existing main application is being migrated step by step to central translation keys."
    )
else:
    st.success("Русский язык выбран для текущего сеанса TraidSim.")
    st.write(
        "Выбранный язык уже используется в новых разделах документации и Hyperopt 2. "
        "Существующий основной интерфейс постепенно переводится на централизованные ключи локализации."
    )

st.divider()
st.subheader(t("settings"))
st.write(f"**{t('tab_overview')} · {t('tab_hyperopt')} · {t('tab_hyperopt2')} · {t('tab_simulation')} · {t('tab_documentation')}**")

st.info(
    "Die Auswahl wird im Streamlit-Sitzungsstatus gespeichert. Eine dauerhafte Speicherung am Benutzerkonto "
    "wird ergänzt, sobald die bestehende Anmeldung eine zentrale Benutzerprofilablage erhält."
    if selected_language == "de"
    else (
        "The selection is stored in the Streamlit session. Permanent storage in the user account will be added "
        "once the existing login has a central user profile store."
        if selected_language == "en"
        else "Выбор сохраняется в текущем сеансе Streamlit. Постоянное хранение в профиле пользователя будет добавлено после создания централизованного хранилища профилей."
    )
)
