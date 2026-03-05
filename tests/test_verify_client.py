import pytest
import respx
from httpx import Response

from src.verify.client import VerifyAPIError, VerifyClient

BASE_URL = "https://test-verify.example.com"


@pytest.fixture
def client() -> VerifyClient:
    return VerifyClient(base_url=BASE_URL)


class TestGetLanguages:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success(self, client: VerifyClient) -> None:
        respx.get(f"{BASE_URL}/languages").mock(
            return_value=Response(200, json={
                "data": [
                    {"id": "uuid-1", "code": "en", "name": "English"},
                    {"id": "uuid-2", "code": "fr", "name": "French"},
                ]
            })
        )
        languages = await client.get_languages()
        assert len(languages) == 2
        assert languages[0].code == "en"
        assert languages[1].name == "French"

    @respx.mock
    @pytest.mark.asyncio
    async def test_caching(self, client: VerifyClient) -> None:
        route = respx.get(f"{BASE_URL}/languages").mock(
            return_value=Response(200, json={
                "data": [{"id": "uuid-1", "code": "en", "name": "English"}]
            })
        )
        await client.get_languages()
        await client.get_languages()
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error(self, client: VerifyClient) -> None:
        respx.get(f"{BASE_URL}/languages").mock(
            return_value=Response(500, json={"detail": "Internal Server Error"})
        )
        with pytest.raises(VerifyAPIError) as exc_info:
            await client.get_languages()
        assert exc_info.value.status_code == 500


class TestGetBalance:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success(self, client: VerifyClient) -> None:
        respx.get(f"{BASE_URL}/user/balance").mock(
            return_value=Response(200, json={"balance": 5000})
        )
        balance = await client.get_balance("test-key")
        assert balance == 5000

    @respx.mock
    @pytest.mark.asyncio
    async def test_unauthorized(self, client: VerifyClient) -> None:
        respx.get(f"{BASE_URL}/user/balance").mock(
            return_value=Response(401, json={"detail": "Unauthorized"})
        )
        with pytest.raises(VerifyAPIError) as exc_info:
            await client.get_balance("bad-key")
        assert exc_info.value.status_code == 401


class TestGetProjects:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success(self, client: VerifyClient) -> None:
        respx.get(f"{BASE_URL}/project").mock(
            return_value=Response(200, json={
                "data": [
                    {
                        "uuid": "proj-1",
                        "client_uuid": "client-1",
                        "title": "Test Project",
                        "status": "COMPLETED",
                        "target_languages": [],
                        "source_files": [],
                        "archived": False,
                        "created_at": "2026-01-01T00:00:00",
                        "modified_at": "2026-01-01T00:00:00",
                    }
                ]
            })
        )
        projects = await client.get_projects("test-key")
        assert len(projects) == 1
        assert projects[0].title == "Test Project"
        assert projects[0].status.value == "COMPLETED"


class TestGetProject:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success(self, client: VerifyClient) -> None:
        respx.get(f"{BASE_URL}/project/proj-1").mock(
            return_value=Response(200, json={
                "data": {
                    "uuid": "proj-1",
                    "client_uuid": "client-1",
                    "title": "Test Project",
                    "status": "ANALYZING",
                    "target_languages": [],
                    "source_files": [],
                    "archived": False,
                    "created_at": "2026-01-01T00:00:00",
                    "modified_at": "2026-01-01T00:00:00",
                }
            })
        )
        project = await client.get_project("test-key", "proj-1")
        assert project.uuid == "proj-1"
        assert project.status.value == "ANALYZING"

    @respx.mock
    @pytest.mark.asyncio
    async def test_with_cost(self, client: VerifyClient) -> None:
        respx.get(f"{BASE_URL}/project/proj-1").mock(
            return_value=Response(200, json={
                "data": {
                    "uuid": "proj-1",
                    "client_uuid": "client-1",
                    "title": "Pending Project",
                    "status": "PENDING_PAYMENT",
                    "target_languages": [],
                    "source_files": [],
                    "archived": False,
                    "created_at": "2026-01-01T00:00:00",
                    "modified_at": "2026-01-01T00:00:00",
                },
                "token_cost": 150,
            })
        )
        project = await client.get_project("test-key", "proj-1")
        assert project.status.value == "PENDING_PAYMENT"

    @respx.mock
    @pytest.mark.asyncio
    async def test_not_found(self, client: VerifyClient) -> None:
        respx.get(f"{BASE_URL}/project/nonexistent").mock(
            return_value=Response(404, json={"detail": "Not found"})
        )
        with pytest.raises(VerifyAPIError) as exc_info:
            await client.get_project("test-key", "nonexistent")
        assert exc_info.value.status_code == 404
