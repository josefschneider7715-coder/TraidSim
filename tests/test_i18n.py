from src.i18n import TRANSLATIONS, localize_phrase, translate


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
