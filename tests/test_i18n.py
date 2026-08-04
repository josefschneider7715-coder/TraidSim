from src.i18n import TRANSLATIONS, localize_phrase, parameter_label, translate


def test_english_ui_translations_are_available() -> None:
    assert translate("saved_watchlist", "en") == "Saved watchlist"
    assert translate("disclaimer", "en").startswith("This is a technical analysis")
    assert localize_phrase("KAUF", "en") == "BUY"
    assert localize_phrase("Gesamtrendite %", "en") == "Total return %"


def test_russian_ui_translations_are_available() -> None:
    assert translate("saved_watchlist", "ru") == "Сохранённый список"
    assert localize_phrase("KAUF", "ru") == "ПОКУПКА"
    assert localize_phrase("Kurs", "ru") == "Цена"


def test_every_language_contains_the_same_ui_keys() -> None:
    german_keys = set(TRANSLATIONS["de"])
    assert set(TRANSLATIONS["en"]) == german_keys
    assert set(TRANSLATIONS["ru"]) == german_keys


def test_dynamic_chart_and_objective_phrases_are_localized() -> None:
    assert localize_phrase("AMZN - Strategiechart", "en") == "AMZN - Strategy chart"
    assert localize_phrase("Maximale Rendite", "ru") == "Максимальная доходность"


def test_hyperopt_parameter_labels_match_ui_areas() -> None:
    assert parameter_label("atr_max_pct", "de") == "ATR – maximale Volatilität (%)"
    assert parameter_label("rsi_max", "en") == "RSI – upper entry threshold"
    assert parameter_label("stoch_period", "ru").startswith("Стохастик –")
    assert parameter_label("unknown_parameter", "de") == "unknown_parameter"
