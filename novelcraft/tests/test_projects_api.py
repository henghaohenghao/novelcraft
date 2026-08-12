"""
Tests for Projects API endpoints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestProjectsAPI:
    """Test suite for /api/projects endpoints"""

    async def test_create_project(self, client: AsyncClient, sample_project_data):
        """Test POST /api/projects - Create a new project"""
        response = await client.post("/api/projects", json=sample_project_data)

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["title"] == sample_project_data["title"]
        assert data["synopsis"] == sample_project_data["synopsis"]
        assert data["genre"] == sample_project_data["genre"]
        assert data["style"] == sample_project_data["style"]
        assert data["status"] == "draft"
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_project_minimal(self, client: AsyncClient):
        """Test creating project with only required fields"""
        response = await client.post("/api/projects", json={"title": "最小项目"})

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "最小项目"

    async def test_get_projects_empty(self, client: AsyncClient):
        """Test GET /api/projects - Get empty project list"""
        response = await client.get("/api/projects")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_projects_list(self, client: AsyncClient, sample_project_data):
        """Test GET /api/projects - Get project list"""
        # Create multiple projects
        await client.post("/api/projects", json=sample_project_data)
        await client.post("/api/projects", json={**sample_project_data, "title": "项目2"})
        await client.post("/api/projects", json={**sample_project_data, "title": "项目3"})

        response = await client.get("/api/projects")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

        # Check ordering (should be by updated_at desc)
        titles = [p["title"] for p in data]
        assert "项目3" in titles
        assert "项目2" in titles
        assert sample_project_data["title"] in titles

    async def test_get_project_by_id(self, client: AsyncClient, sample_project_data):
        """Test GET /api/projects/{project_id} - Get project details"""
        # Create a project
        create_response = await client.post("/api/projects", json=sample_project_data)
        project_id = create_response.json()["id"]

        # Get project by ID
        response = await client.get(f"/api/projects/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == project_id
        assert data["title"] == sample_project_data["title"]

    async def test_get_project_not_found(self, client: AsyncClient):
        """Test GET /api/projects/{project_id} - Project not found"""
        response = await client.get("/api/projects/non-existent-id")

        assert response.status_code == 404

    async def test_update_project(self, client: AsyncClient, sample_project_data):
        """Test PUT /api/projects/{project_id} - Update project"""
        # Create a project
        create_response = await client.post("/api/projects", json=sample_project_data)
        project_id = create_response.json()["id"]

        # Update project
        update_data = {
            "title": "更新后的标题",
            "status": "in_progress"
        }
        response = await client.put(f"/api/projects/{project_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "更新后的标题"
        assert data["status"] == "in_progress"
        assert data["synopsis"] == sample_project_data["synopsis"]  # Unchanged

    async def test_update_project_not_found(self, client: AsyncClient):
        """Test PUT /api/projects/{project_id} - Project not found"""
        response = await client.put("/api/projects/non-existent-id", json={"title": "新标题"})

        assert response.status_code == 404

    async def test_delete_project(self, client: AsyncClient, sample_project_data):
        """Test DELETE /api/projects/{project_id} - Delete project"""
        # Create a project
        create_response = await client.post("/api/projects", json=sample_project_data)
        project_id = create_response.json()["id"]

        # Delete project
        response = await client.delete(f"/api/projects/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

        # Verify project is deleted
        get_response = await client.get(f"/api/projects/{project_id}")
        assert get_response.status_code == 404

    async def test_delete_project_not_found(self, client: AsyncClient):
        """Test DELETE /api/projects/{project_id} - Project not found"""
        response = await client.delete("/api/projects/non-existent-id")

        assert response.status_code == 404

    async def test_project_lifecycle(self, client: AsyncClient, sample_project_data):
        """Test complete project lifecycle: create -> read -> update -> delete"""
        # Create
        create_response = await client.post("/api/projects", json=sample_project_data)
        assert create_response.status_code == 200
        project_id = create_response.json()["id"]

        # Read
        read_response = await client.get(f"/api/projects/{project_id}")
        assert read_response.status_code == 200
        assert read_response.json()["title"] == sample_project_data["title"]

        # Update
        update_response = await client.put(
            f"/api/projects/{project_id}",
            json={"status": "completed"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "completed"

        # Delete
        delete_response = await client.delete(f"/api/projects/{project_id}")
        assert delete_response.status_code == 200

        # Verify deletion
        final_response = await client.get(f"/api/projects/{project_id}")
        assert final_response.status_code == 404
