import logging
import time
from pathlib import Path

import httpx

from .models import (
    CreateProjectResponse,
    GetLanguagesResponse,
    GetProjectResponse,
    GetProjectsResponse,
    GetProjectWithCostResponse,
    GetTokenBalanceResponse,
    Language,
    Project,
)

logger = logging.getLogger(__name__)

LANGUAGE_CACHE_TTL_SECONDS = 3600


class VerifyAPIError(Exception):
    """Raised when the Verify API returns an error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Verify API error {status_code}: {detail}")


class VerifyClient:
    """Async client for the Straker Verify API."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._language_cache: list[Language] | None = None
        self._language_cache_time: float = 0

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def _check_response(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                body = response.json()
                detail = body.get("detail", response.text)
            except Exception:
                detail = response.text
            raise VerifyAPIError(response.status_code, str(detail))

    async def get_languages(self) -> list[Language]:
        """Fetch all supported languages. Results are cached for 1 hour."""
        now = time.time()
        if self._language_cache and (now - self._language_cache_time) < LANGUAGE_CACHE_TTL_SECONDS:
            return self._language_cache

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self._base_url}/languages")
            self._check_response(response)
            parsed = GetLanguagesResponse.model_validate(response.json())
            self._language_cache = parsed.data
            self._language_cache_time = now
            logger.info("Fetched %d languages from Verify API", len(parsed.data))
            return parsed.data

    async def get_balance(self, api_key: str) -> int:
        """Get user token balance. Also serves as API key validation."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/user/balance",
                headers=self._headers(api_key),
            )
            self._check_response(response)
            parsed = GetTokenBalanceResponse.model_validate(response.json())
            return parsed.balance

    async def create_project(
        self,
        api_key: str,
        files: list[Path],
        language_ids: list[str],
        title: str,
        confirmation_required: bool = True,
        workflow_id: str | None = None,
        callback_uri: str | None = None,
    ) -> CreateProjectResponse:
        """Create a new translation project via multipart form upload."""
        file_tuples = []
        for file_path in files:
            file_tuples.append(("files", (file_path.name, file_path.read_bytes())))

        data: dict[str, str | list[str]] = {
            "title": title,
            "confirmation_required": str(confirmation_required).lower(),
        }

        for lang_id in language_ids:
            if "languages" not in data:
                data["languages"] = []
            if isinstance(data["languages"], list):
                data["languages"].append(lang_id)

        if workflow_id:
            data["workflow_id"] = workflow_id
        if callback_uri:
            data["callback_uri"] = callback_uri

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/project",
                headers=self._headers(api_key),
                data=data,
                files=file_tuples,
            )
            self._check_response(response)
            return CreateProjectResponse.model_validate(response.json())

    async def confirm_project(self, api_key: str, project_id: str) -> None:
        """Confirm a project for payment processing."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self._base_url}/project/confirm",
                headers=self._headers(api_key),
                data={"project_id": project_id},
            )
            self._check_response(response)

    async def get_project(self, api_key: str, project_id: str) -> Project:
        """Get project details by ID."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/project/{project_id}",
                headers=self._headers(api_key),
            )
            self._check_response(response)
            body = response.json()
            # Response may include token_cost when PENDING_PAYMENT
            if "token_cost" in body:
                parsed = GetProjectWithCostResponse.model_validate(body)
            else:
                parsed = GetProjectResponse.model_validate(body)
            return parsed.data

    async def get_projects(self, api_key: str, page: int = 1, page_size: int = 10) -> list[Project]:
        """List projects for the authenticated user."""
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self._base_url}/project",
                headers=self._headers(api_key),
                params={"page": page, "page_size": page_size},
            )
            self._check_response(response)
            parsed = GetProjectsResponse.model_validate(response.json())
            return parsed.data

    async def download_file(self, api_key: str, file_id: str) -> bytes:
        """Download a file by its UUID."""
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(
                f"{self._base_url}/file/{file_id}",
                headers=self._headers(api_key),
            )
            self._check_response(response)
            return response.content
