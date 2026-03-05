from src.bot.keyboards import (
    LANG_CANCEL,
    LANG_DONE,
    LANG_PAGE_PREFIX,
    LANG_SELECT_PREFIX,
    LANGUAGES_PER_PAGE,
    build_confirm_keyboard,
    build_language_keyboard,
)
from src.verify.models import Language


def _make_languages(count: int) -> list[Language]:
    """Helper to create a list of test languages."""
    return [
        Language(id=f"uuid-{i}", code=f"lang-{i}", name=f"Language {i}")
        for i in range(count)
    ]


class TestBuildLanguageKeyboard:
    def test_single_page(self) -> None:
        languages = _make_languages(5)
        keyboard = build_language_keyboard(languages, selected_ids=set(), page=0)
        rows = keyboard.inline_keyboard
        # 5 language buttons + 1 nav row + 1 action row
        assert len(rows) == 7
        assert rows[0][0].callback_data == f"{LANG_SELECT_PREFIX}uuid-0"

    def test_selected_languages_show_checkmark(self) -> None:
        languages = _make_languages(3)
        keyboard = build_language_keyboard(languages, selected_ids={"uuid-1"}, page=0)
        rows = keyboard.inline_keyboard
        assert "\u2705" in rows[1][0].text
        assert "\u2705" not in rows[0][0].text

    def test_pagination(self) -> None:
        languages = _make_languages(20)
        keyboard = build_language_keyboard(languages, selected_ids=set(), page=0)
        nav_row = keyboard.inline_keyboard[LANGUAGES_PER_PAGE]
        # First page: no Prev, has page info, has Next
        assert len(nav_row) == 2  # page counter + Next
        assert nav_row[1].callback_data == f"{LANG_PAGE_PREFIX}1"

    def test_second_page(self) -> None:
        languages = _make_languages(20)
        keyboard = build_language_keyboard(languages, selected_ids=set(), page=1)
        nav_row = keyboard.inline_keyboard[LANGUAGES_PER_PAGE]
        # Has Prev, page counter, Next
        assert len(nav_row) == 3
        assert nav_row[0].callback_data == f"{LANG_PAGE_PREFIX}0"

    def test_done_button_shows_count(self) -> None:
        languages = _make_languages(5)
        keyboard = build_language_keyboard(languages, selected_ids={"uuid-0", "uuid-1"}, page=0)
        action_row = keyboard.inline_keyboard[-1]
        assert any(LANG_DONE == btn.callback_data for btn in action_row)
        done_btn = [btn for btn in action_row if btn.callback_data == LANG_DONE][0]
        assert "2 selected" in done_btn.text

    def test_cancel_always_present(self) -> None:
        languages = _make_languages(3)
        keyboard = build_language_keyboard(languages, selected_ids=set(), page=0)
        action_row = keyboard.inline_keyboard[-1]
        assert any(LANG_CANCEL == btn.callback_data for btn in action_row)

    def test_search_filter(self) -> None:
        languages = [
            Language(id="uuid-en", code="en", name="English"),
            Language(id="uuid-fr", code="fr", name="French"),
            Language(id="uuid-de", code="de", name="German"),
        ]
        keyboard = build_language_keyboard(languages, selected_ids=set(), page=0, search_query="fre")
        lang_rows = keyboard.inline_keyboard[:-2]  # exclude nav + action
        assert len(lang_rows) == 1
        assert "French" in lang_rows[0][0].text

    def test_empty_search_shows_all(self) -> None:
        languages = _make_languages(5)
        keyboard = build_language_keyboard(languages, selected_ids=set(), page=0, search_query="")
        lang_rows = keyboard.inline_keyboard[:-2]
        assert len(lang_rows) == 5


class TestBuildConfirmKeyboard:
    def test_has_confirm_and_cancel(self) -> None:
        keyboard = build_confirm_keyboard()
        buttons = keyboard.inline_keyboard[0]
        assert len(buttons) == 2
        assert buttons[0].callback_data == "confirm_yes"
        assert buttons[1].callback_data == "confirm_no"
