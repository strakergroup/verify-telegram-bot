"""Pydantic models for the Straker Order API (ECFMG certified translations)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ECFMGLanguage(BaseModel):
    """A language option returned by GET /languages?type=ecfmg.

    API response shape: {"code": "Spanish_Latin_America", "name": "Spanish (Latin America)", "tier": 1}
    """

    code: str = ""
    name: str = ""
    tier: int = 0

    @property
    def display_name(self) -> str:
        return self.name or self.code


class Country(BaseModel):
    """A country option returned by GET /countries.

    API response shape: {"id": 124, "name": "New Zealand (Aotearoa)"}
    """

    id: int = 0
    name: str = ""

    @property
    def id_str(self) -> str:
        return str(self.id)

    @property
    def display_name(self) -> str:
        return self.name or self.id_str


class FileUploadResponse(BaseModel):
    """Response from POST /file/save."""

    success: bool
    id: str = ""


class JobFileInfo(BaseModel):
    """File metadata in the job response."""

    filename: str = ""
    wordcount: int = 0
    pagecount: int = 0
    ext: str = ""
    charactercount: int = 0
    autoQuote: int = Field(default=0, alias="autoQuote")

    @field_validator("autoQuote", mode="before")
    @classmethod
    def _coerce_auto_quote(cls, v: object) -> int:
        if v is None or v == "":
            return 0
        return int(v)

    model_config = {"populate_by_name": True}


class JobQuote(BaseModel):
    """A quote within the job response."""

    price: str = "0.00"
    subtotal: str = "0.00"
    tax: str = "0.00"
    tax_name: str = ""
    total: str = "0.00"
    postage: str = "0.00"
    leadtime: int = 0
    ndays: int = 0
    translators: int = 0
    serviceType: str = ""
    certype: str = ""
    index: int = 0
    paymentLink: str = ""

    model_config = {"populate_by_name": True}


class JobResponse(BaseModel):
    """Response from POST /job."""

    status: bool = False
    jobid: int = 0
    jobuuid: str = ""
    jobtype: str = ""
    certype: str = ""
    firstname: str = ""
    lastname: str = ""
    sl: str = ""
    tl: str = ""
    currency: str = ""
    cSymbl: str = Field(default="$", alias="cSymbl")
    quotes: list[JobQuote] = []
    files: list[JobFileInfo] = []
    autoquote: int = 0
    charflag: bool = False
    sendviapost: str = "no"
    emailto: str = ""
    emailfrom: str = ""
    sl_code: str = ""

    model_config = {"populate_by_name": True}


ECFMG_TARGET_LANG_CODE = "English_US"
ECFMG_TARGET_LANG_LABEL = "English (USA)"

ECFMG_CONSTANTS = {
    "certtype": "ECFMG",
    "jobtype": "ECFMG",
    "categoryvalue": "Personal",
    "category": "C961A300-6825-456F-B7C30375C6BCCEC8",
    "subcategory": "D1902175-F13C-4875-924C9CEFC577849E",
    "bPolice": "2",
    "bAd": "1",
}
