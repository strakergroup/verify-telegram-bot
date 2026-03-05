import pytest
import respx
from httpx import Response

from src.order.client import OrderAPIError, OrderClient

BASE_URL = "https://test-order.example.com"


@pytest.fixture
def client() -> OrderClient:
    return OrderClient(base_url=BASE_URL)


class TestFromurl:
    def test_hostname_extraction(self, client: OrderClient) -> None:
        assert client.fromurl == "test-order.example.com"

    def test_hostname_with_path(self) -> None:
        c = OrderClient("https://order.example.com/some/path")
        assert c.fromurl == "order.example.com"


class TestGetECFMGLanguages:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success_wrapped_format(self, client: OrderClient) -> None:
        respx.get(f"{BASE_URL}/languages").mock(
            return_value=Response(200, json={
                "languages": [
                    {"code": "Spanish_Latin_America", "name": "Spanish (Latin America)", "tier": 1},
                    {"code": "English_US", "name": "English (USA)", "tier": 1},
                ]
            })
        )
        languages = await client.get_ecfmg_languages()
        assert len(languages) == 2
        assert languages[0].code == "Spanish_Latin_America"
        assert languages[0].display_name == "Spanish (Latin America)"
        assert languages[0].tier == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_success_bare_list(self, client: OrderClient) -> None:
        respx.get(f"{BASE_URL}/languages").mock(
            return_value=Response(200, json=[
                {"code": "French", "name": "French (France)", "tier": 1},
            ])
        )
        languages = await client.get_ecfmg_languages()
        assert len(languages) == 1
        assert languages[0].code == "French"

    @respx.mock
    @pytest.mark.asyncio
    async def test_caching(self, client: OrderClient) -> None:
        route = respx.get(f"{BASE_URL}/languages").mock(
            return_value=Response(200, json={
                "languages": [
                    {"code": "English_US", "name": "English (USA)", "tier": 1},
                ]
            })
        )
        await client.get_ecfmg_languages()
        await client.get_ecfmg_languages()
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error(self, client: OrderClient) -> None:
        respx.get(f"{BASE_URL}/languages").mock(
            return_value=Response(500, json={"message": "Server Error"})
        )
        with pytest.raises(OrderAPIError) as exc_info:
            await client.get_ecfmg_languages()
        assert exc_info.value.status_code == 500


class TestGetCountries:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success_wrapped_format(self, client: OrderClient) -> None:
        respx.get(f"{BASE_URL}/countries").mock(
            return_value=Response(200, json={
                "countries": [
                    {"id": 32, "name": "Canada"},
                    {"id": 124, "name": "New Zealand (Aotearoa)"},
                ]
            })
        )
        countries = await client.get_countries()
        assert len(countries) == 2
        assert countries[0].id == 32
        assert countries[0].id_str == "32"
        assert countries[1].display_name == "New Zealand (Aotearoa)"

    @respx.mock
    @pytest.mark.asyncio
    async def test_success_bare_list(self, client: OrderClient) -> None:
        respx.get(f"{BASE_URL}/countries").mock(
            return_value=Response(200, json=[
                {"id": 32, "name": "Canada"},
            ])
        )
        countries = await client.get_countries()
        assert len(countries) == 1
        assert countries[0].id_str == "32"

    @respx.mock
    @pytest.mark.asyncio
    async def test_caching(self, client: OrderClient) -> None:
        route = respx.get(f"{BASE_URL}/countries").mock(
            return_value=Response(200, json={
                "countries": [
                    {"id": 32, "name": "Canada"},
                ]
            })
        )
        await client.get_countries()
        await client.get_countries()
        assert route.call_count == 1


class TestUploadFile:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success(self, client: OrderClient, tmp_path) -> None:
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4 test content")

        respx.post(f"{BASE_URL}/file/save").mock(
            return_value=Response(200, json={"success": True, "id": "12953"})
        )
        result = await client.upload_file(
            file_path=test_file,
            session_token="TEST-SESSION-UUID",
        )
        assert result.success is True
        assert result.id == "12953"

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_error(self, client: OrderClient, tmp_path) -> None:
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4 test content")

        respx.post(f"{BASE_URL}/file/save").mock(
            return_value=Response(500, text="Internal Server Error")
        )
        with pytest.raises(OrderAPIError) as exc_info:
            await client.upload_file(
                file_path=test_file,
                session_token="TEST-SESSION-UUID",
            )
        assert exc_info.value.status_code == 500


class TestCreateJob:
    @respx.mock
    @pytest.mark.asyncio
    async def test_success(self, client: OrderClient) -> None:
        respx.post(f"{BASE_URL}/job").mock(
            return_value=Response(200, json={
                "status": True,
                "jobid": 831030,
                "jobuuid": "C8AA6B39-3EEF-4EF3-863EEA0F3E18E553",
                "jobtype": "ECFMG",
                "certype": "ECFMG",
                "firstname": "John",
                "lastname": "Doe",
                "sl": "Spanish (Latin America)",
                "tl": "English (USA)",
                "currency": "NZD",
                "cSymbl": "$",
                "quotes": [
                    {
                        "price": "83.56",
                        "subtotal": "83.56",
                        "tax": "12.53",
                        "tax_name": "GST",
                        "total": "96.09",
                        "postage": "0.00",
                        "leadtime": 48,
                        "ndays": 2,
                        "translators": 1,
                        "serviceType": "Translation",
                        "certype": "ECFMG",
                        "index": 1,
                        "paymentLink": "https://pay.example.com/pay?id=ABC123",
                    }
                ],
                "files": [
                    {
                        "filename": "test.pdf",
                        "wordcount": 72,
                        "pagecount": 1,
                        "ext": "pdf",
                        "charactercount": 356,
                        "autoQuote": 1,
                    }
                ],
                "autoquote": 1,
                "charflag": False,
                "sendviapost": "no",
                "emailto": "test@example.com",
                "emailfrom": "noreply@example.com",
                "sl_code": "Spanish_Latin_America",
            })
        )
        result = await client.create_job(
            firstname="John",
            lastname="Doe",
            email="test@example.com",
            phone="1234567890",
            source_lang="Spanish_Latin_America",
            target_lang="English_US",
            country="124",
            session_token="TEST-SESSION-UUID",
        )
        assert result.status is True
        assert result.jobid == 831030
        assert result.currency == "NZD"
        assert len(result.quotes) == 1
        assert result.quotes[0].total == "96.09"
        assert "pay.example.com" in result.quotes[0].paymentLink
        assert len(result.files) == 1
        assert result.files[0].filename == "test.pdf"

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_error(self, client: OrderClient) -> None:
        respx.post(f"{BASE_URL}/job").mock(
            return_value=Response(500, json={"message": "Job creation failed"})
        )
        with pytest.raises(OrderAPIError) as exc_info:
            await client.create_job(
                firstname="John",
                lastname="Doe",
                email="test@example.com",
                phone="1234567890",
                source_lang="Spanish_Latin_America",
                target_lang="English_US",
                country="124",
                session_token="TEST-SESSION-UUID",
            )
        assert exc_info.value.status_code == 500
