"""Async client for the Straker Order API (ECFMG certified translations)."""

import logging
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .models import (
    Country,
    ECFMGLanguage,
    FileUploadResponse,
    JobResponse,
    ECFMG_CONSTANTS,
)

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600


class OrderAPIError(Exception):
    """Raised when the Order API returns an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Order API error {status_code}: {detail}")


class OrderClient:
    """Async client for the Straker Order API."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._lang_cache: list[ECFMGLanguage] | None = None
        self._lang_cache_time: float = 0
        self._country_cache: list[Country] | None = None
        self._country_cache_time: float = 0

    @property
    def fromurl(self) -> str:
        """Extract hostname from base URL for the fromurl form field."""
        return urlparse(self._base_url).hostname or ""

    def _check_response(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("message", body.get("detail", response.text))
            except Exception:
                detail = response.text
            raise OrderAPIError(response.status_code, str(detail))

    async def get_ecfmg_languages(self) -> list[ECFMGLanguage]:
        """Fetch available ECFMG languages. Results are cached for 1 hour."""
        now = time.time()
        if self._lang_cache and (now - self._lang_cache_time) < CACHE_TTL_SECONDS:
            return self._lang_cache

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/languages",
                params={"type": "ecfmg"},
            )
            self._check_response(response)
            raw = response.json()
            if isinstance(raw, list):
                languages = [ECFMGLanguage.model_validate(item) for item in raw]
            else:
                data = raw.get("data", raw.get("languages", []))
                languages = [ECFMGLanguage.model_validate(item) for item in data]

            self._lang_cache = languages
            self._lang_cache_time = now
            logger.info("Fetched %d ECFMG languages from Order API", len(languages))
            return languages

    async def get_countries(self) -> list[Country]:
        """Fetch available countries. Results are cached for 1 hour."""
        now = time.time()
        if self._country_cache and (now - self._country_cache_time) < CACHE_TTL_SECONDS:
            return self._country_cache

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self._base_url}/countries")
            self._check_response(response)
            raw = response.json()
            if isinstance(raw, list):
                countries = [Country.model_validate(item) for item in raw]
            else:
                data = raw.get("data", raw.get("countries", []))
                countries = [Country.model_validate(item) for item in data]

            self._country_cache = countries
            self._country_cache_time = now
            logger.info("Fetched %d countries from Order API", len(countries))
            return countries

    async def upload_file(
        self,
        file_path: Path,
        session_token: str,
        file_uuid: str | None = None,
    ) -> FileUploadResponse:
        """Upload a file via POST /file/save (multipart form).

        Args:
            file_path: Local path to the file to upload.
            session_token: Session UUID that ties this upload to the job.
            file_uuid: Per-file UUID. Auto-generated if not provided.
        """
        if not file_uuid:
            file_uuid = str(uuid.uuid4())

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/file/save",
                data={
                    "token": session_token,
                    "fileUUID": file_uuid,
                },
                files={
                    "file": (file_path.name, file_path.read_bytes()),
                },
            )
            self._check_response(response)
            result = FileUploadResponse.model_validate(response.json())
            logger.info(
                "Uploaded file %s (id=%s, session=%s)",
                file_path.name, result.id, session_token[:8],
            )
            return result

    async def create_job(
        self,
        *,
        firstname: str,
        lastname: str,
        email: str,
        phone: str,
        source_lang: str,
        target_lang: str,
        country: str,
        session_token: str,
        notes: str = "",
        accept_terms: bool = True,
        marketing_optin: bool = True,
    ) -> JobResponse:
        """Create an ECFMG job via POST /job (form-urlencoded).

        Fixed ECFMG constants are merged automatically.
        """
        data = {
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "phone": phone,
            "sl": source_lang,
            "tl": target_lang,
            "country": country,
            "session": session_token,
            "notes": notes,
            "bPolice": "2" if accept_terms else "1",
            "bAd": "1" if marketing_optin else "0",
            "fromurl": self.fromurl,
            **{k: v for k, v in ECFMG_CONSTANTS.items() if k not in ("bPolice", "bAd")},
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self._base_url}/job",
                data=data,
            )
            self._check_response(response)
            raw_json = response.json()
            logger.debug("Order API /job raw response: %s", raw_json)
            result = JobResponse.model_validate(raw_json)
            logger.info(
                "Created ECFMG job %d (uuid=%s) for %s – quotes=%d",
                result.jobid, result.jobuuid, email, len(result.quotes),
            )
            return result
