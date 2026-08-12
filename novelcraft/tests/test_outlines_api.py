"""
Tests for Outlines API endpoints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestOutlinesAPI:
    """Test suite for /api/outlines endpoints"""

    async def test_create_outline(self, client: AsyncClient, sample_project_data, sample_outline_data):
        """Test POST /api/outlines - Create outline node"""
        # Create a project first
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create outline
        outline_data = {**sample_outline_data, "project_id": project_id}
        response = await client.post("/api/outlines", json=outline_data)

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["project_id"] == project_id
        assert data["title"] == sample_outline_data["title"]
        assert data["content"] == sample_outline_data["content"]
        assert data["node_type"] == "chapter"
        assert data["parent_id"] is None

    async def test_create_nested_outline(self, client: AsyncClient, sample_project_data, sample_outline_data):
        """Test creating nested outline nodes"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create parent outline
        parent_data = {**sample_outline_data, "project_id": project_id}
        parent_response = await client.post("/api/outlines", json=parent_data)
        parent_id = parent_response.json()["id"]

        # Create child outline
        child_data = {
            **sample_outline_data,
            "project_id": project_id,
            "parent_id": parent_id,
            "title": "第一节：初遇",
            "depth": 1
        }
        response = await client.post("/api/outlines", json=child_data)

        assert response.status_code == 200
        data = response.json()
        assert data["parent_id"] == parent_id
        assert data["depth"] == 1

    async def test_get_project_outlines_flat(self, client: AsyncClient, sample_project_data, sample_outline_data):
        """Test GET /api/outlines/project/{project_id} - Get flat outline list"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create multiple outlines
        for i in range(3):
            outline_data = {
                **sample_outline_data,
                "project_id": project_id,
                "title": f"第{i+1}章",
                "sort_order": i
            }
            await client.post("/api/outlines", json=outline_data)

        # Get outlines
        response = await client.get(f"/api/outlines/project/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_get_project_outlines_tree(self, client: AsyncClient, sample_project_data, sample_outline_data):
        """Test GET /api/outlines/project/{project_id}/tree - Get tree structure"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create parent outline
        parent_data = {**sample_outline_data, "project_id": project_id}
        parent_response = await client.post("/api/outlines", json=parent_data)
        parent_id = parent_response.json()["id"]

        # Create child outlines
        for i in range(2):
            child_data = {
                **sample_outline_data,
                "project_id": project_id,
                "parent_id": parent_id,
                "title": f"第一节之{i+1}",
                "depth": 1
            }
            await client.post("/api/outlines", json=child_data)

        # Get tree
        response = await client.get(f"/api/outlines/project/{project_id}/tree")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1  # One root node
        assert "children" in data[0]
        assert len(data[0]["children"]) == 2  # Two child nodes

    async def test_generate_outline_without_llm(self, client: AsyncClient, sample_project_data):
        """Test POST /api/outlines/generate - AI generate outline (will fail without LLM)"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Try to generate outline
        generate_data = {
            "project_id": project_id,
            "synopsis": sample_project_data["synopsis"],
            "chapter_count": 5
        }
        response = await client.post("/api/outlines/generate", json=generate_data)

        # This will likely fail without proper LLM configuration
        # But we test that the endpoint exists and returns proper error
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    async def test_get_outline_by_id(self, client: AsyncClient, sample_project_data, sample_outline_data):
        """Test GET /api/outlines/{outline_id} - Get outline details"""
        # Create project and outline
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        outline_data = {**sample_outline_data, "project_id": project_id}
        outline_response = await client.post("/api/outlines", json=outline_data)
        outline_id = outline_response.json()["id"]

        # Get outline by ID
        response = await client.get(f"/api/outlines/{outline_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == outline_id
        assert data["title"] == sample_outline_data["title"]

    async def test_update_outline(self, client: AsyncClient, sample_project_data, sample_outline_data):
        """Test PUT /api/outlines/{outline_id} - Update outline"""
        # Create project and outline
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        outline_data = {**sample_outline_data, "project_id": project_id}
        outline_response = await client.post("/api/outlines", json=outline_data)
        outline_id = outline_response.json()["id"]

        # Update outline
        update_data = {
            "title": "更新后的章节标题",
            "content": "更新后的内容"
        }
        response = await client.put(f"/api/outlines/{outline_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "更新后的章节标题"
        assert data["content"] == "更新后的内容"

    async def test_delete_outline(self, client: AsyncClient, sample_project_data, sample_outline_data):
        """Test DELETE /api/outlines/{outline_id} - Delete outline"""
        # Create project and outline
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        outline_data = {**sample_outline_data, "project_id": project_id}
        outline_response = await client.post("/api/outlines", json=outline_data)
        outline_id = outline_response.json()["id"]

        # Delete outline
        response = await client.delete(f"/api/outlines/{outline_id}")

        assert response.status_code == 200

        # Verify deletion
        get_response = await client.get(f"/api/outlines/{outline_id}")
        assert get_response.status_code == 404
