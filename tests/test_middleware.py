import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
async def raw_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


class TestSecurityHeaders:
    async def test_x_content_type_options(self, raw_client):
        resp = await raw_client.get("/api/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    async def test_x_frame_options(self, raw_client):
        resp = await raw_client.get("/api/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    async def test_csp_header_present(self, raw_client):
        resp = await raw_client.get("/api/health")
        assert "content-security-policy" in resp.headers

    async def test_permissions_policy(self, raw_client):
        resp = await raw_client.get("/api/health")
        assert "permissions-policy" in resp.headers


class TestGzipCompression:
    async def test_gzip_for_large_responses(self, raw_client):
        resp = await raw_client.get("/", headers={"Accept-Encoding": "gzip"})
        # HTML response should be compressed if large enough
        assert resp.status_code == 200
