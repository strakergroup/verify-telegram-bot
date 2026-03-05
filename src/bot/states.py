from enum import IntEnum


class AuthStates(IntEnum):
    """Conversation states for the authentication flow."""

    AWAITING_API_KEY = 0


class TranslateStates(IntEnum):
    """Conversation states for the translation workflow."""

    AWAITING_FILE = 10
    AWAITING_LANGUAGES = 11
    AWAITING_TITLE = 12
    CONFIRM = 13


class ECFMGStates(IntEnum):
    """Conversation states for the ECFMG certified translation flow."""

    AWAITING_FIRSTNAME = 20
    AWAITING_LASTNAME = 21
    AWAITING_EMAIL = 22
    AWAITING_PHONE = 23
    AWAITING_SOURCE_LANG = 24
    AWAITING_COUNTRY = 26
    AWAITING_FILE = 27
    AWAITING_TERMS = 28
    AWAITING_NOTES = 29
    CONFIRM = 30
