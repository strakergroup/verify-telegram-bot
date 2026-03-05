import logging
import math

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..order.models import Country, ECFMGLanguage
from ..verify.models import Language

logger = logging.getLogger(__name__)

LANGUAGES_PER_PAGE = 8
ITEMS_PER_PAGE = 8

# Callback data prefixes
LANG_SELECT_PREFIX = "lang_sel:"
LANG_PAGE_PREFIX = "lang_page:"
LANG_DONE = "lang_done"
LANG_CANCEL = "lang_cancel"
CONFIRM_YES = "confirm_yes"
CONFIRM_NO = "confirm_no"

# ECFMG callback data prefixes
ECFMG_LANG_PREFIX = "ecfmg_lang:"
ECFMG_COUNTRY_PREFIX = "ecfmg_ctry:"
ECFMG_COUNTRY_PAGE_PREFIX = "ecfmg_ctry_pg:"
ECFMG_TERMS_ACCEPT = "ecfmg_terms_yes"
ECFMG_TERMS_DECLINE = "ecfmg_terms_no"
ECFMG_NOTES_SKIP = "ecfmg_notes_skip"
ECFMG_CONFIRM_YES = "ecfmg_confirm_yes"
ECFMG_CONFIRM_NO = "ecfmg_confirm_no"


def build_language_keyboard(
    languages: list[Language],
    selected_ids: set[str],
    page: int = 0,
    search_query: str = "",
) -> InlineKeyboardMarkup:
    """Build a paginated inline keyboard for language selection.

    Each language button shows a checkmark if selected. Pagination buttons
    navigate through pages. A 'Done' button finalises the selection.
    """
    filtered = languages
    if search_query:
        query_lower = search_query.lower()
        filtered = [
            lang for lang in languages
            if query_lower in lang.name.lower() or query_lower in lang.code.lower()
        ]

    total_pages = max(1, math.ceil(len(filtered) / LANGUAGES_PER_PAGE))
    page = max(0, min(page, total_pages - 1))

    start_idx = page * LANGUAGES_PER_PAGE
    end_idx = start_idx + LANGUAGES_PER_PAGE
    page_languages = filtered[start_idx:end_idx]

    keyboard: list[list[InlineKeyboardButton]] = []

    for lang in page_languages:
        prefix = "\u2705 " if lang.id in selected_ids else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"{prefix}{lang.name} ({lang.code})",
                callback_data=f"{LANG_SELECT_PREFIX}{lang.id}",
            )
        ])

    # Pagination row
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="\u25c0 Prev", callback_data=f"{LANG_PAGE_PREFIX}{page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="Next \u25b6", callback_data=f"{LANG_PAGE_PREFIX}{page + 1}")
        )
    keyboard.append(nav_buttons)

    # Selection count + action row
    count = len(selected_ids)
    action_buttons: list[InlineKeyboardButton] = []
    if count > 0:
        action_buttons.append(
            InlineKeyboardButton(text=f"\u2705 Done ({count} selected)", callback_data=LANG_DONE)
        )
    action_buttons.append(
        InlineKeyboardButton(text="\u274c Cancel", callback_data=LANG_CANCEL)
    )
    keyboard.append(action_buttons)

    return InlineKeyboardMarkup(keyboard)


def build_confirm_keyboard() -> InlineKeyboardMarkup:
    """Build a Confirm / Cancel inline keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="\u2705 Confirm & Submit", callback_data=CONFIRM_YES),
            InlineKeyboardButton(text="\u274c Cancel", callback_data=CONFIRM_NO),
        ]
    ])


# ── ECFMG keyboards ─────────────────────────────────────────────────────────


def build_ecfmg_language_keyboard(
    languages: list[ECFMGLanguage],
) -> InlineKeyboardMarkup:
    """Build an inline keyboard for selecting a single ECFMG language."""
    keyboard: list[list[InlineKeyboardButton]] = []
    for lang in languages:
        keyboard.append([
            InlineKeyboardButton(
                text=lang.display_name,
                callback_data=f"{ECFMG_LANG_PREFIX}{lang.code}",
            )
        ])
    keyboard.append([
        InlineKeyboardButton(text="\u274c Cancel", callback_data=LANG_CANCEL),
    ])
    return InlineKeyboardMarkup(keyboard)


def build_country_keyboard(
    countries: list[Country],
    page: int = 0,
    search_query: str = "",
) -> InlineKeyboardMarkup:
    """Build a paginated inline keyboard for country selection."""
    filtered = countries
    if search_query:
        query_lower = search_query.lower()
        filtered = [c for c in countries if query_lower in c.display_name.lower()]

    total_pages = max(1, math.ceil(len(filtered) / ITEMS_PER_PAGE))
    page = max(0, min(page, total_pages - 1))

    start_idx = page * ITEMS_PER_PAGE
    page_items = filtered[start_idx : start_idx + ITEMS_PER_PAGE]

    keyboard: list[list[InlineKeyboardButton]] = []
    for country in page_items:
        keyboard.append([
            InlineKeyboardButton(
                text=country.display_name,
                callback_data=f"{ECFMG_COUNTRY_PREFIX}{country.id_str}",
            )
        ])

    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="\u25c0 Prev", callback_data=f"{ECFMG_COUNTRY_PAGE_PREFIX}{page - 1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(text="Next \u25b6", callback_data=f"{ECFMG_COUNTRY_PAGE_PREFIX}{page + 1}")
        )
    keyboard.append(nav_buttons)

    keyboard.append([
        InlineKeyboardButton(text="\u274c Cancel", callback_data=LANG_CANCEL),
    ])
    return InlineKeyboardMarkup(keyboard)


def build_terms_keyboard() -> InlineKeyboardMarkup:
    """Build a T&C acceptance keyboard for ECFMG."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="\u2705 Accept", callback_data=ECFMG_TERMS_ACCEPT),
            InlineKeyboardButton(text="\u274c Decline", callback_data=ECFMG_TERMS_DECLINE),
        ]
    ])


def build_ecfmg_notes_keyboard() -> InlineKeyboardMarkup:
    """Build a keyboard with a Skip option for the notes step."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="\u23ed Skip", callback_data=ECFMG_NOTES_SKIP)],
        [InlineKeyboardButton(text="\u274c Cancel", callback_data=LANG_CANCEL)],
    ])


def build_ecfmg_confirm_keyboard() -> InlineKeyboardMarkup:
    """Build a Confirm / Cancel keyboard for ECFMG order."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="\u2705 Order Now", callback_data=ECFMG_CONFIRM_YES),
            InlineKeyboardButton(text="\u274c Cancel", callback_data=ECFMG_CONFIRM_NO),
        ]
    ])
