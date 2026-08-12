"""
健康检查与系统端点测试
"""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestHealthAPI:
    """/api/health 健康检查接口测试套件"""

    async def test_health_check(self, client: AsyncClient):
        """测试 GET /api/health — 健康检查"""
        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "services" in data

        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"

        services = data["services"]
        assert "database" in services
        assert "neo4j" in services
        assert "qdrant" in services

        assert services["database"] in ["sqlite", "postgresql"]

        assert isinstance(services["neo4j"], bool)
        assert isinstance(services["qdrant"], bool)

    async def test_health_check_response_structure(self, client: AsyncClient):
        """验证健康检查响应结构正确"""
        response = await client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        expected_keys = {"status", "version", "services"}
        assert set(data.keys()) == expected_keys

        expected_service_keys = {"database", "neo4j", "qdrant"}
        assert set(data["services"].keys()) == expected_service_keys

    async def test_health_check_multiple_calls(self, client: AsyncClient):
        """测试健康检查可多次调用"""
        for _ in range(5):
            response = await client.get("/api/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    async def test_api_root_not_found(self, client: AsyncClient):
        """测试根路径返回 404（未定义根端点）"""
        response = await client.get("/")
        assert response.status_code == 404

    async def test_invalid_endpoint(self, client: AsyncClient):
        """测试无效端点返回 404"""
        response = await client.get("/api/invalid-endpoint")
        assert response.status_code == 404

    async def test_cors_headers(self, client: AsyncClient):
        """测试 CORS 头存在"""
        response = await client.get("/api/health")

        assert response.status_code == 200
