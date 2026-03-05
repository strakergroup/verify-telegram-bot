"""Tests for ECFMG models and keyboard builders."""

import pytest

from src.bot.keyboards import (
    ECFMG_CONFIRM_NO,
    ECFMG_CONFIRM_YES,
    ECFMG_COUNTRY_PAGE_PREFIX,
    ECFMG_COUNTRY_PREFIX,
    ECFMG_LANG_PREFIX,
    ECFMG_NOTES_SKIP,
    ECFMG_TERMS_ACCEPT,
    ECFMG_TERMS_DECLINE,
    build_country_keyboard,
    build_ecfmg_confirm_keyboard,
    build_ecfmg_language_keyboard,
    build_ecfmg_notes_keyboard,
    build_terms_keyboard,
)
from src.order.models import (
    ECFMG_CONSTANTS,
    Country,
    ECFMGLanguage,
    FileUploadResponse,
    JobQuote,
    JobResponse,
)


class TestECFMGModels:
    def test_ecfmg_language_display_name_from_name(self) -> None:
        lang = ECFMGLanguage(code="Spanish_Latin_America", name="Spanish (Latin America)", tier=1)
        assert lang.display_name == "Spanish (Latin America)"
        assert lang.code == "Spanish_Latin_America"
        assert lang.tier == 1

    def test_ecfmg_language_display_name_fallback(self) -> None:
        lang = ECFMGLanguage(code="French", name="")
        assert lang.display_name == "French"

    def test_country_display_name(self) -> None:
        c = Country(id=124, name="New Zealand (Aotearoa)")
        assert c.display_name == "New Zealand (Aotearoa)"
        assert c.id_str == "124"

    def test_country_id_str(self) -> None:
        c = Country(id=32, name="Canada")
        assert c.id_str == "32"

    def test_file_upload_response(self) -> None:
        r = FileUploadResponse(success=True, id="12953")
        assert r.success is True
        assert r.id == "12953"

    def test_job_response_with_quotes(self) -> None:
        r = JobResponse(
            status=True,
            jobid=831030,
            currency="NZD",
            cSymbl="$",
            quotes=[
                JobQuote(
                    price="83.56",
                    total="96.09",
                    tax="12.53",
                    tax_name="GST",
                    paymentLink="https://pay.example.com/pay",
                )
            ],
        )
        assert r.jobid == 831030
        assert r.quotes[0].total == "96.09"
        assert r.quotes[0].paymentLink.startswith("https://")

    def test_ecfmg_constants_has_required_fields(self) -> None:
        assert "certtype" in ECFMG_CONSTANTS
        assert "jobtype" in ECFMG_CONSTANTS
        assert "category" in ECFMG_CONSTANTS
        assert "subcategory" in ECFMG_CONSTANTS
        assert ECFMG_CONSTANTS["jobtype"] == "ECFMG"


class TestECFMGLanguageKeyboard:
    def test_builds_with_languages(self) -> None:
        languages = [
            ECFMGLanguage(code="Spanish_Latin_America", name="Spanish (Latin America)", tier=1),
            ECFMGLanguage(code="English_US", name="English (USA)", tier=1),
        ]
        kb = build_ecfmg_language_keyboard(languages)
        buttons = kb.inline_keyboard
        assert len(buttons) == 3  # 2 languages + cancel row
        assert buttons[0][0].callback_data == f"{ECFMG_LANG_PREFIX}Spanish_Latin_America"
        assert buttons[1][0].text == "English (USA)"

    def test_empty_language_list(self) -> None:
        kb = build_ecfmg_language_keyboard([])
        buttons = kb.inline_keyboard
        assert len(buttons) == 1  # just cancel row


class TestCountryKeyboard:
    @pytest.fixture
    def countries(self) -> list[Country]:
        return [Country(id=i, name=f"Country {i}") for i in range(20)]

    def test_first_page(self, countries: list[Country]) -> None:
        kb = build_country_keyboard(countries, page=0)
        buttons = kb.inline_keyboard
        assert buttons[0][0].callback_data == f"{ECFMG_COUNTRY_PREFIX}0"
        nav_row = buttons[-2]
        has_next = any(
            btn.callback_data and btn.callback_data.startswith(ECFMG_COUNTRY_PAGE_PREFIX)
            for btn in nav_row
        )
        assert has_next

    def test_search_filter(self, countries: list[Country]) -> None:
        kb = build_country_keyboard(countries, page=0, search_query="Country 1")
        buttons = kb.inline_keyboard
        country_buttons = [
            b for row in buttons for b in row
            if b.callback_data and b.callback_data.startswith(ECFMG_COUNTRY_PREFIX)
        ]
        for btn in country_buttons:
            assert "1" in btn.text


class TestTermsKeyboard:
    def test_has_accept_and_decline(self) -> None:
        kb = build_terms_keyboard()
        buttons = kb.inline_keyboard
        all_data = [b.callback_data for row in buttons for b in row]
        assert ECFMG_TERMS_ACCEPT in all_data
        assert ECFMG_TERMS_DECLINE in all_data


class TestNotesKeyboard:
    def test_has_skip(self) -> None:
        kb = build_ecfmg_notes_keyboard()
        buttons = kb.inline_keyboard
        all_data = [b.callback_data for row in buttons for b in row]
        assert ECFMG_NOTES_SKIP in all_data


class TestConfirmKeyboard:
    def test_has_order_and_cancel(self) -> None:
        kb = build_ecfmg_confirm_keyboard()
        buttons = kb.inline_keyboard
        all_data = [b.callback_data for row in buttons for b in row]
        assert ECFMG_CONFIRM_YES in all_data
        assert ECFMG_CONFIRM_NO in all_data
