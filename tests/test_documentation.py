from src.documentation import DOCUMENTATION


def test_documentation_exists_in_every_language() -> None:
    assert set(DOCUMENTATION) == {"de", "en", "ru"}
    for content in DOCUMENTATION.values():
        assert "Hyperopt" in content
        assert "Simulation" in content or "Симуляция" in content
        assert "Architecture" in content or "Architektur" in content or "Архитектура" in content


def test_german_manual_explains_controls_criteria_and_results() -> None:
    manual = DOCUMENTATION["de"]
    assert "## 3. Einstellungen" in manual
    assert "## 7. Die zehn Kriterien" in manual
    assert "### Konvergenz" in manual
    assert "### Empfehlung vollständig in Simulation übernehmen" in manual
    assert "## 10. Kriterien-Telemetrie und Ranglisten" in manual
    assert "## 11. Technische Architektur" in manual
