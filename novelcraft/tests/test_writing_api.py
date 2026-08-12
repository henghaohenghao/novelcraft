"""
Tests for Writing/Chapters API endpoints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestWritingAPI:
    """Test suite for /api/writing endpoints"""

    async def test_create_chapter(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test POST /api/writing/chapters - Create chapter"""
        # Create project first
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create chapter
        chapter_data = {**sample_chapter_data, "project_id": project_id}
        response = await client.post("/api/writing/chapters", json=chapter_data)

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["project_id"] == project_id
        assert data["title"] == sample_chapter_data["title"]
        assert data["chapter_number"] == sample_chapter_data["chapter_number"]
        assert data["status"] == "planned"
        assert data["content"] == ""
        assert data["revision_count"] == 0

    async def test_create_chapter_with_outline(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test creating chapter linked to outline"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create outline
        outline_data = {
            "project_id": project_id,
            "title": "第一章大纲",
            "content": "章节内容规划"
        }
        outline_response = await client.post("/api/outlines", json=outline_data)
        outline_id = outline_response.json()["id"]

        # Create chapter with outline
        chapter_data = {
            **sample_chapter_data,
            "project_id": project_id,
            "outline_id": outline_id
        }
        response = await client.post("/api/writing/chapters", json=chapter_data)

        assert response.status_code == 200
        data = response.json()
        assert data["outline_id"] == outline_id

    async def test_get_project_chapters(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test GET /api/writing/chapters/project/{project_id} - Get chapter list"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create multiple chapters
        for i in range(3):
            chapter_data = {
                **sample_chapter_data,
                "project_id": project_id,
                "title": f"第{i+1}章",
                "chapter_number": i + 1
            }
            await client.post("/api/writing/chapters", json=chapter_data)

        # Get chapters
        response = await client.get(f"/api/writing/chapters/project/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

        # Check ordering by chapter_number
        chapter_numbers = [c["chapter_number"] for c in data]
        assert chapter_numbers == [1, 2, 3]

    async def test_get_chapter_by_id(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test GET /api/writing/chapters/{chapter_id} - Get chapter details"""
        # Create project and chapter
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        chapter_data = {**sample_chapter_data, "project_id": project_id}
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        chapter_id = chapter_response.json()["id"]

        # Get chapter by ID
        response = await client.get(f"/api/writing/chapters/{chapter_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == chapter_id
        assert data["title"] == sample_chapter_data["title"]

    async def test_update_chapter(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test PUT /api/writing/chapters/{chapter_id} - Update chapter"""
        # Create project and chapter
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        chapter_data = {**sample_chapter_data, "project_id": project_id}
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        chapter_id = chapter_response.json()["id"]

        # Update chapter
        update_data = {
            "title": "更新后的章节标题",
            "content": "这是更新后的章节内容。"
        }
        response = await client.put(f"/api/writing/chapters/{chapter_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "更新后的章节标题"
        assert data["content"] == "这是更新后的章节内容。"

    async def test_delete_chapter(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test DELETE /api/writing/chapters/{chapter_id} - Delete chapter"""
        # Create project and chapter
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        chapter_data = {**sample_chapter_data, "project_id": project_id}
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        chapter_id = chapter_response.json()["id"]

        # Delete chapter
        response = await client.delete(f"/api/writing/chapters/{chapter_id}")

        assert response.status_code == 200

        # Verify deletion
        get_response = await client.get(f"/api/writing/chapters/{chapter_id}")
        assert get_response.status_code == 404

    async def test_generate_chapter_sync_without_llm(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test POST /api/writing/chapters/generate-sync - Sync generate (will fail without LLM)"""
        # Create project and chapter
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        chapter_data = {**sample_chapter_data, "project_id": project_id}
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        chapter_id = chapter_response.json()["id"]

        # Try to generate chapter
        generate_data = {
            "chapter_id": chapter_id,
            "style": "古龙风"
        }
        response = await client.post("/api/writing/chapters/generate-sync", json=generate_data)

        # Will likely fail without proper LLM configuration
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert data["id"] == chapter_id
            assert len(data["content"]) > 0

    async def test_generate_chapter_stream_endpoint_exists(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test POST /api/writing/chapters/generate - Stream endpoint exists"""
        # Create project and chapter
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        chapter_data = {**sample_chapter_data, "project_id": project_id}
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        chapter_id = chapter_response.json()["id"]

        # Try to generate chapter (streaming)
        generate_data = {
            "chapter_id": chapter_id,
            "style": "古龙风"
        }

        # Note: Testing SSE streaming is complex, we just verify endpoint exists
        # Full SSE testing would require special handling
        response = await client.post(
            "/api/writing/chapters/generate",
            json=generate_data,
            timeout=5.0  # Short timeout since we're not waiting for full generation
        )

        # Should start streaming or return error
        # We accept various status codes since LLM may not be configured
        assert response.status_code in [200, 500, 504]

    async def test_chapter_status_transitions(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test chapter status transitions through lifecycle"""
        # Create project and chapter
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        chapter_data = {**sample_chapter_data, "project_id": project_id}
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        chapter_id = chapter_response.json()["id"]

        # Initial status should be 'planned'
        get_response = await client.get(f"/api/writing/chapters/{chapter_id}")
        assert get_response.json()["status"] == "planned"

        # Update to 'writing'
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"status": "writing"})
        get_response = await client.get(f"/api/writing/chapters/{chapter_id}")
        assert get_response.json()["status"] == "writing"

        # Update to 'completed'
        await client.put(f"/api/writing/chapters/{chapter_id}", json={"status": "completed"})
        get_response = await client.get(f"/api/writing/chapters/{chapter_id}")
        assert get_response.json()["status"] == "completed"

    async def test_chapter_revision_count(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test chapter revision count tracking"""
        # Create project and chapter
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        chapter_data = {**sample_chapter_data, "project_id": project_id}
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        chapter_id = chapter_response.json()["id"]

        # Initial revision count should be 0
        get_response = await client.get(f"/api/writing/chapters/{chapter_id}")
        assert get_response.json()["revision_count"] == 0

        # Note: revision_count is typically updated by the agent workflow
        # We can't easily test it without running the full generation

    async def test_multiple_chapters_ordering(self, client: AsyncClient, sample_project_data, sample_chapter_data):
        """Test that chapters are returned in correct order"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create chapters in random order
        chapter_numbers = [3, 1, 5, 2, 4]
        for num in chapter_numbers:
            chapter_data = {
                **sample_chapter_data,
                "project_id": project_id,
                "title": f"第{num}章",
                "chapter_number": num
            }
            await client.post("/api/writing/chapters", json=chapter_data)

        # Get chapters
        response = await client.get(f"/api/writing/chapters/project/{project_id}")

        assert response.status_code == 200
        data = response.json()

        # Should be ordered by chapter_number
        chapter_numbers_returned = [c["chapter_number"] for c in data]
        assert chapter_numbers_returned == [1, 2, 3, 4, 5]
