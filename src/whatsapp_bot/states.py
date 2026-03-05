"""Conversation states for the WhatsApp bot state machine."""

from enum import Enum


class ConversationState(str, Enum):
    IDLE = "idle"
    AWAITING_API_KEY = "awaiting_api_key"
    AWAITING_FILE = "awaiting_file"
    AWAITING_LANGUAGES = "awaiting_languages"
    AWAITING_TITLE = "awaiting_title"
    AWAITING_CONFIRM = "awaiting_confirm"

    # ECFMG certified translation flow
    ECFMG_FIRSTNAME = "ecfmg_firstname"
    ECFMG_LASTNAME = "ecfmg_lastname"
    ECFMG_EMAIL = "ecfmg_email"
    ECFMG_PHONE = "ecfmg_phone"
    ECFMG_SOURCE_LANG = "ecfmg_source_lang"
    ECFMG_COUNTRY = "ecfmg_country"
    ECFMG_FILE = "ecfmg_file"
    ECFMG_TERMS = "ecfmg_terms"
    ECFMG_NOTES = "ecfmg_notes"
    ECFMG_CONFIRM = "ecfmg_confirm"
