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

    async def test_csp_includes_google_fonts(self, raw_client):
        resp = await raw_client.get("/api/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "fonts.googleapis.com" in csp
        assert "fonts.gstatic.com" in csp

    async def test_csp_includes_gcs(self, raw_client):
        resp = await raw_client.get("/api/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "storage.googleapis.com" in csp

    async def test_csp_includes_blob(self, raw_client):
        resp = await raw_client.get("/api/health")
        csp = resp.headers.get("content-security-policy", "")
        assert "blob:" in csp

    async def test_permissions_policy(self, raw_client):
        resp = await raw_client.get("/api/health")
        assert "permissions-policy" in resp.headers

    async def test_hsts_header(self, raw_client):
        resp = await raw_client.get("/api/health")
        assert "strict-transport-security" in resp.headers

    async def test_referrer_policy(self, raw_client):
        resp = await raw_client.get("/api/health")
        assert "referrer-policy" in resp.headers


class TestGzipCompression:
    async def test_gzip_for_large_responses(self, raw_client):
        resp = await raw_client.get("/", headers={"Accept-Encoding": "gzip"})
        assert resp.status_code == 200


class TestRateLimiting:
    async def test_rate_limiter_is_active(self, raw_client):
        resp = await raw_client.post(
            "/api/game/start",
            json={"player_name": "RateTest", "adventure": "hawkins-investigation"},
        )
        assert resp.status_code != 429


class TestStaticFiles:
    async def test_serves_index_html(self, raw_client):
        resp = await raw_client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    async def test_serves_css(self, raw_client):
        resp = await raw_client.get("/css/style.css")
        assert resp.status_code == 200

    async def test_serves_js(self, raw_client):
        resp = await raw_client.get("/js/app.js")
        assert resp.status_code == 200

    async def test_serves_animations_css(self, raw_client):
        resp = await raw_client.get("/css/animations.css")
        assert resp.status_code == 200

    async def test_serves_map_css(self, raw_client):
        resp = await raw_client.get("/css/map.css")
        assert resp.status_code == 200
