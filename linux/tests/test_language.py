"""
Tests for the language manager module.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from splitwire.core.language import (
    LanguageManager,
    LanguageError,
)


class TestLanguageManager:
    """Tests for LanguageManager class."""

    @pytest.fixture
    def temp_lang_dir(self):
        """Create a temporary language directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lang_dir = Path(tmpdir)

            # Create English translation
            en_data = {
                "app": {"name": "SplitWire-Turkey", "title": "Test App"},
                "buttons": {"install": "Install", "remove": "Remove"},
                "messages": {
                    "success": "Operation successful",
                    "error": "An error occurred: {0}",
                },
                "nested": {"level1": {"level2": {"key": "Deep value"}}},
            }
            with open(lang_dir / "en.json", "w") as f:
                json.dump(en_data, f)

            # Create Turkish translation
            tr_data = {
                "app": {"name": "SplitWire-Turkey", "title": "Test Uygulamasi"},
                "buttons": {"install": "Kur", "remove": "Kaldir"},
                "messages": {
                    "success": "Islem basarili",
                    "error": "Bir hata olustu: {0}",
                },
            }
            with open(lang_dir / "tr.json", "w") as f:
                json.dump(tr_data, f)

            yield lang_dir

    @pytest.fixture
    def lang_manager(self, temp_lang_dir):
        """Create a LanguageManager with English test translations."""
        return LanguageManager(language="en", resources_dir=temp_lang_dir)

    def test_get_text_simple(self, lang_manager):
        """Test getting simple translation."""
        result = lang_manager.get_text("buttons", "install")
        assert result == "Install"

    def test_get_text_nested(self, lang_manager):
        """Test getting nested translation."""
        result = lang_manager.get_text("app", "name")
        assert result == "SplitWire-Turkey"

    def test_get_text_deep_nested(self, lang_manager):
        """Test getting deeply nested translation."""
        result = lang_manager.get_text("nested", "level1", "level2", "key")
        assert result == "Deep value"

    def test_get_text_missing_key(self, lang_manager):
        """Test handling of missing translation key."""
        result = lang_manager.get_text("nonexistent", "key")
        assert "nonexistent.key" in result  # Returns key path as fallback

    def test_format_text(self, lang_manager):
        """Test text formatting with placeholders."""
        # Get the error message template
        template = lang_manager.get_text("messages", "error")
        # Format it
        result = template.format("Connection failed")
        assert "Connection failed" in result

    def test_language_switch(self, temp_lang_dir):
        """Test switching languages."""
        manager = LanguageManager(language="en", resources_dir=temp_lang_dir)
        assert manager.get_text("buttons", "install") == "Install"

        # Switch to Turkish
        manager.set_language("tr")
        assert manager.get_text("buttons", "install") == "Kur"

    def test_fallback_to_english(self, temp_lang_dir):
        """Test fallback to English when key missing in current language."""
        manager = LanguageManager(language="tr", resources_dir=temp_lang_dir)

        # Turkish doesn't have nested.level1.level2.key, should fall back
        result = manager.get_text("nested", "level1", "level2", "key")
        assert result == "Deep value"


class TestFallbackChain:
    """Tests for the language manager fallback chain behavior."""

    @pytest.fixture
    def temp_lang_dir(self):
        """Create a temporary language directory with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lang_dir = Path(tmpdir)

            # English: has all keys including "nested" and "en_only"
            en_data = {
                "app": {"name": "SplitWire-Turkey"},
                "buttons": {"install": "Install", "remove": "Remove"},
                "nested": {"level1": {"key": "English deep value"}},
                "en_only": {"special": "English-only key"},
            }
            with open(lang_dir / "en.json", "w") as f:
                json.dump(en_data, f)

            # Turkish: missing "nested" and "en_only" sections
            tr_data = {
                "app": {"name": "SplitWire-Turkey"},
                "buttons": {"install": "Kur", "remove": "Kaldir"},
            }
            with open(lang_dir / "tr.json", "w") as f:
                json.dump(tr_data, f)

            yield lang_dir

    def test_fallback_returns_english_for_missing_key(self, temp_lang_dir):
        """Test that get_text returns English fallback for missing key."""
        manager = LanguageManager(language="tr", resources_dir=temp_lang_dir)
        result = manager.get_text("en_only", "special")
        assert result == "English-only key"

    def test_fallback_returns_key_path_when_missing_everywhere(
        self, temp_lang_dir
    ):
        """Test that get_text returns key path when missing from all."""
        manager = LanguageManager(language="tr", resources_dir=temp_lang_dir)
        result = manager.get_text("totally", "missing")
        assert result == "totally.missing"

    def test_fallback_works_when_language_is_english(self, temp_lang_dir):
        """Test that fallback works when current language IS English."""
        manager = LanguageManager(language="en", resources_dir=temp_lang_dir)
        # Key exists in en.json -- should return it
        result = manager.get_text("en_only", "special")
        assert result == "English-only key"

    def test_fallback_english_never_returns_empty(self, temp_lang_dir):
        """Test that get_text never returns empty string."""
        manager = LanguageManager(language="en", resources_dir=temp_lang_dir)
        result = manager.get_text("nonexistent", "key")
        assert result != ""
        assert result == "nonexistent.key"

    def test_fallback_warning_logged_on_english_fallback(self, temp_lang_dir):
        """Test that logger.warning fires when falling back to English."""
        manager = LanguageManager(language="tr", resources_dir=temp_lang_dir)
        with patch("splitwire.core.language.logger") as mock_logger:
            manager.get_text("en_only", "special")
            mock_logger.warning.assert_any_call(
                "[LANG] Fallback to English for key: en_only.special"
            )

    def test_missing_key_warning_logged(self, temp_lang_dir):
        """Test that logger.warning fires for completely missing key."""
        manager = LanguageManager(language="tr", resources_dir=temp_lang_dir)
        with patch("splitwire.core.language.logger") as mock_logger:
            manager.get_text("totally", "missing")
            mock_logger.warning.assert_any_call(
                "[LANG] Missing translation: totally.missing"
            )

    def test_no_fallback_warning_when_key_exists_in_current_lang(
        self, temp_lang_dir
    ):
        """Test no fallback warning when key exists in current language."""
        manager = LanguageManager(language="tr", resources_dir=temp_lang_dir)
        with patch("splitwire.core.language.logger") as mock_logger:
            result = manager.get_text("buttons", "install")
            assert result == "Kur"
            # Should NOT have fallback warning for this key
            for call_args in mock_logger.warning.call_args_list:
                assert "Fallback to English for key: buttons.install" not in str(
                    call_args
                )


class TestLanguageError:
    """Tests for LanguageError exception."""

    def test_language_error_message(self):
        """Test LanguageError exception message."""
        error = LanguageError("Translation file not found")
        assert str(error) == "Translation file not found"

    def test_language_error_inheritance(self):
        """Test that LanguageError is an Exception."""
        error = LanguageError("Test error")
        assert isinstance(error, Exception)


class TestTranslationFiles:
    """Tests for translation file structure."""

    @pytest.fixture
    def real_lang_dir(self):
        """Get the real language directory."""
        lang_dir = Path(__file__).parent.parent / "src" / "splitwire" / "resources" / "languages"
        if lang_dir.exists():
            return lang_dir
        pytest.skip("Language directory not found")

    def test_all_languages_exist(self, real_lang_dir):
        """Test that all expected language files exist."""
        expected_files = ["en.json", "tr.json", "ru.json", "es.json"]
        for filename in expected_files:
            assert (real_lang_dir / filename).exists(), f"Missing: {filename}"

    def test_language_files_valid_json(self, real_lang_dir):
        """Test that all language files are valid JSON."""
        for lang_file in real_lang_dir.glob("*.json"):
            with open(lang_file) as f:
                try:
                    data = json.load(f)
                    assert isinstance(data, dict)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {lang_file.name}: {e}")

    def test_required_keys_exist(self, real_lang_dir):
        """Test that required translation keys exist in all files."""
        required_keys = ["app", "buttons", "messages", "status"]

        for lang_file in real_lang_dir.glob("*.json"):
            with open(lang_file) as f:
                data = json.load(f)
                for key in required_keys:
                    assert key in data, f"Missing key '{key}' in {lang_file.name}"
