"""
Language/Localization manager for SplitWire-Turkey Linux.

Provides multi-language support using JSON translation files.
Compatible with the Windows version's language file format.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class LanguageError(Exception):
    """Exception raised for language-related errors."""


class LanguageManager:
    """Manages application translations from JSON files.

    Loads language strings from JSON files and provides
    easy access to translations via get_text().

    Attributes:
        LANGUAGES: Mapping of language codes to display names.
        DEFAULT_LANGUAGE: Fallback language code ("en").
    """

    # Supported languages
    LANGUAGES: ClassVar[dict[str, str]] = {
        "tr": "Türkçe",
        "en": "English",
        "ru": "Русский",
        "es": "Español",
    }

    DEFAULT_LANGUAGE = "en"

    def __init__(
        self,
        language: str = DEFAULT_LANGUAGE,
        resources_dir: Path | None = None,
    ) -> None:
        """Initialize language manager.

        Args:
            language: Language code (tr, en, ru, es).
            resources_dir: Override resources directory (for testing).

        Example:
            >>> mgr = LanguageManager("en")
            >>> mgr.language
            'en'
        """
        self._language = language if language in self.LANGUAGES else self.DEFAULT_LANGUAGE
        self._translations: dict[str, Any] = {}
        self._fallback_translations: dict[str, Any] = {}

        # Determine resources directory
        if resources_dir:
            self._resources_dir = resources_dir
        else:
            # Default: relative to this file's location
            self._resources_dir = Path(__file__).parent.parent / "resources" / "languages"

        # Load translations
        self._load_translations()

    @property
    def language(self) -> str:
        """Get current language code."""
        return self._language

    @property
    def language_name(self) -> str:
        """Get current language name."""
        return self.LANGUAGES.get(self._language, "Unknown")

    @classmethod
    def get_available_languages(cls) -> dict[str, str]:
        """Get dictionary of available languages (code to name).

        Returns:
            Copy of the LANGUAGES mapping.

        Example:
            >>> langs = LanguageManager.get_available_languages()
            >>> "en" in langs
            True
        """
        return cls.LANGUAGES.copy()

    def set_language(self, language: str) -> bool:
        """Change the current language and reload translations.

        Args:
            language: Language code (tr, en, ru, es).

        Returns:
            True if language was changed successfully.

        Example:
            >>> mgr = LanguageManager("en")
            >>> mgr.set_language("tr")
            True
        """
        if language not in self.LANGUAGES:
            logger.warning(f"[LANG] Unsupported language: {language}")
            return False

        if language == self._language:
            return True

        logger.info(f"[LANG] Changing language from {self._language} to {language}")
        self._language = language
        self._load_translations()
        return True

    def _load_translations(self) -> None:
        """Load translations for current language."""
        logger.info(f"[LANG] Loading language: {self._language}")

        # Always load fallback (English) regardless of current language
        fallback_file = self._resources_dir / f"{self.DEFAULT_LANGUAGE}.json"
        self._fallback_translations = self._load_json_file(fallback_file)

        # Load current language
        lang_file = self._resources_dir / f"{self._language}.json"
        self._translations = self._load_json_file(lang_file)

        # Log loaded keys count
        key_count = self._count_keys(self._translations)
        logger.debug(f"[LANG] Loaded {key_count} translation keys for {self._language}")

        # Clear the cache when translations change
        self.get_text.cache_clear()

    def _count_keys(self, data: dict, prefix: str = "") -> int:
        """Count total number of translation keys in a dictionary."""
        count = 0
        for key, value in data.items():
            if isinstance(value, dict):
                count += self._count_keys(value, f"{prefix}{key}.")
            else:
                count += 1
        return count

    def _load_json_file(self, path: Path) -> dict[str, Any]:
        """Load a JSON translation file."""
        if not path.exists():
            logger.warning(f"[LANG] Language file not found: {path}")
            return {}

        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"[LANG] Failed to load language file {path}: {e}")
            return {}

    @lru_cache(maxsize=512)  # noqa: B019 -- singleton instance, no leak risk
    def get_text(self, *keys: str, default: str = "") -> str:
        """Get translated text for the given key path.

        Supports nested keys via multiple args or dot notation.

        Args:
            *keys: Key path (multiple args or dot-separated).
            default: Default value if key not found.

        Returns:
            Translated string, English fallback, or key path.

        Example:
            >>> mgr = LanguageManager("en")
            >>> mgr.get_text("buttons", "save")
            'Save'
        """
        # Handle both get_text("a", "b") and get_text("a.b")
        key_path = keys[0].split(".") if len(keys) == 1 and "." in keys[0] else list(keys)

        # Try current language first
        result = self._get_nested(self._translations, key_path)
        if result is not None:
            return result

        # Fall back to English
        result = self._get_nested(self._fallback_translations, key_path)
        if result is not None:
            key_str = ".".join(key_path)
            logger.warning(f"[LANG] Fallback to English for key: {key_str}")
            return result

        # Missing from all languages -- return key path as bug indicator
        key_str = ".".join(key_path)
        logger.warning(f"[LANG] Missing translation: {key_str}")

        # Return default or key path as fallback
        return default if default else key_str

    def _get_nested(self, data: dict, keys: list[str]) -> str | None:
        """Get nested value from dictionary."""
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        # Return only if it's a string
        return current if isinstance(current, str) else None

    def format_text(self, *keys: str, **kwargs: object) -> str:
        """Get translated text and format with named arguments.

        Uses Python str.format() for ``{name}`` placeholders.

        Args:
            *keys: Key path for the translation.
            **kwargs: Named format arguments.

        Returns:
            Formatted translated string.

        Example:
            >>> mgr = LanguageManager("en")
            >>> mgr.format_text("greeting", name="World")
            'Hello, World!'
        """
        text = self.get_text(*keys)

        # Handle both {name} and {0} style placeholders
        try:
            if kwargs:
                # Try named format first
                return text.format(**kwargs)
            return text
        except (KeyError, IndexError):
            return text

    def format_text_positional(self, *keys: str, args: tuple[object, ...] = ()) -> str:
        """Get translated text and format with positional arguments.

        For Windows compatibility with ``{0}``, ``{1}`` placeholders.

        Args:
            *keys: Key path for the translation.
            args: Positional format arguments.

        Returns:
            Formatted translated string.

        Example:
            >>> mgr = LanguageManager("en")
            >>> mgr.format_text_positional("msg", args=("A",))
            'Value: A'
        """
        text = self.get_text(*keys)
        try:
            return text.format(*args)
        except (KeyError, IndexError):
            return text

    def get_section(self, section: str) -> dict[str, str]:
        """Get all translations in a named section.

        Args:
            section: Section name (e.g., "buttons", "messages").

        Returns:
            Dictionary mapping keys to translated text strings.

        Example:
            >>> mgr = LanguageManager("en")
            >>> btns = mgr.get_section("buttons")
            >>> isinstance(btns, dict)
            True
        """
        result = self._translations.get(section, {})
        if isinstance(result, dict):
            # Filter to only string values
            return {k: v for k, v in result.items() if isinstance(v, str)}
        return {}

    def reload(self) -> None:
        """Reload translations from disk and clear cache."""
        self._load_translations()


# Global instance for convenience
_language_manager: LanguageManager | None = None


def get_language_manager() -> LanguageManager:
    """Get the global LanguageManager singleton.

    Returns:
        The shared LanguageManager instance.
    """
    global _language_manager
    if _language_manager is None:
        _language_manager = LanguageManager()
    return _language_manager


def init_language_manager(
    language: str = LanguageManager.DEFAULT_LANGUAGE,
) -> LanguageManager:
    """Initialize the global LanguageManager with a language.

    Args:
        language: Language code to activate.

    Returns:
        Newly created LanguageManager instance.
    """
    global _language_manager
    _language_manager = LanguageManager(language)
    return _language_manager


def get_text(*keys: str, default: str = "") -> str:
    """Get translated text via the global manager.

    Args:
        *keys: Key path for the translation.
        default: Fallback if key is missing.

    Returns:
        Translated string.
    """
    return get_language_manager().get_text(*keys, default=default)


def format_text(*keys: str, **kwargs: object) -> str:
    """Get and format translated text via the global manager.

    Args:
        *keys: Key path for the translation.
        **kwargs: Named format arguments.

    Returns:
        Formatted translated string.
    """
    return get_language_manager().format_text(*keys, **kwargs)


def set_language(language: str) -> bool:
    """Set the current language via the global manager.

    Args:
        language: Language code to switch to.

    Returns:
        True if language was changed successfully.
    """
    return get_language_manager().set_language(language)


def get_current_language() -> str:
    """Get current language code from the global manager.

    Returns:
        Active language code string (e.g. "en").
    """
    return get_language_manager().language


# Alias for Windows compatibility
_ = get_text
