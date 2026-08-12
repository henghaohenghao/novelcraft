"""
Frontend Integration Tests
Tests frontend API calls and page functionality
"""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestFrontendIntegration:
    """Integration tests simulating frontend workflows"""

    async def test_complete_project_workflow(self, client: AsyncClient, sample_project_data):
        """Test complete workflow: create project -> outline -> characters -> chapter"""
        # Step 1: Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        assert project_response.status_code == 200
        project_id = project_response.json()["id"]

        # Step 2: Generate outline
        outline_generate_data = {
            "project_id": project_id,
            "synopsis": sample_project_data["synopsis"],
            "chapter_count": 3
        }
        # Note: This will fail without LLM, but we test the flow
        outline_response = await client.post("/api/outlines/generate", json=outline_generate_data)
        # Accept both success and failure
        assert outline_response.status_code in [200, 500]

        # Step 3: Create outline manually if generation failed
        if outline_response.status_code != 200:
            outline_data = {
                "project_id": project_id,
                "title": "第一章：开端",
                "content": "故事的开始"
            }
            outline_response = await client.post("/api/outlines", json=outline_data)
            assert outline_response.status_code == 200

        # Step 4: Get outlines tree
        tree_response = await client.get(f"/api/outlines/project/{project_id}/tree")
        assert tree_response.status_code == 200
        outlines = tree_response.json()
        assert len(outlines) > 0

        # Step 5: Generate characters
        char_generate_response = await client.post(
            f"/api/characters/generate-from-synopsis?project_id={project_id}&synopsis={sample_project_data['synopsis']}"
        )
        # Accept both success and failure
        assert char_generate_response.status_code in [200, 500]

        # Step 6: Create character manually if generation failed
        if char_generate_response.status_code != 200:
            character_data = {
                "project_id": project_id,
                "name": "主角",
                "description": "故事的主角"
            }
            char_response = await client.post("/api/characters", json=character_data)
            assert char_response.status_code == 200

        # Step 7: Get characters
        characters_response = await client.get(f"/api/characters/project/{project_id}")
        assert characters_response.status_code == 200
        characters = characters_response.json()
        assert len(characters) > 0

        # Step 8: Create chapter
        chapter_data = {
            "project_id": project_id,
            "title": "第一章",
            "chapter_number": 1
        }
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        assert chapter_response.status_code == 200
        chapter_id = chapter_response.json()["id"]

        # Step 9: Get chapters
        chapters_response = await client.get(f"/api/writing/chapters/project/{project_id}")
        assert chapters_response.status_code == 200
        chapters = chapters_response.json()
        assert len(chapters) == 1

        # Step 10: Get project graph
        graph_response = await client.get(f"/api/characters/project/{project_id}/graph")
        assert graph_response.status_code == 200
        graph = graph_response.json()
        assert "nodes" in graph
        assert "edges" in graph

    async def test_project_list_page_workflow(self, client: AsyncClient, sample_project_data):
        """Test workflow for project list page"""
        # Initial state: empty list
        list_response = await client.get("/api/projects")
        assert list_response.status_code == 200
        initial_count = len(list_response.json())

        # Create project
        create_response = await client.post("/api/projects", json=sample_project_data)
        assert create_response.status_code == 200

        # Refresh list
        list_response = await client.get("/api/projects")
        assert list_response.status_code == 200
        assert len(list_response.json()) == initial_count + 1

        # Delete project
        project_id = create_response.json()["id"]
        delete_response = await client.delete(f"/api/projects/{project_id}")
        assert delete_response.status_code == 200

        # Verify list updated
        list_response = await client.get("/api/projects")
        assert list_response.status_code == 200
        assert len(list_response.json()) == initial_count

    async def test_project_detail_page_workflow(self, client: AsyncClient, sample_project_data):
        """Test workflow for project detail page with all tabs"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Tab 1: Outline tab - fetch outlines
        outlines_response = await client.get(f"/api/outlines/project/{project_id}/tree")
        assert outlines_response.status_code == 200

        # Tab 2: Characters tab - fetch characters
        characters_response = await client.get(f"/api/characters/project/{project_id}")
        assert characters_response.status_code == 200

        # Tab 3: Writing tab - fetch chapters
        chapters_response = await client.get(f"/api/writing/chapters/project/{project_id}")
        assert chapters_response.status_code == 200

        # Tab 4: Graph tab - fetch graph
        graph_response = await client.get(f"/api/characters/project/{project_id}/graph")
        assert graph_response.status_code == 200

    async def test_outline_creation_from_ui(self, client: AsyncClient, sample_project_data):
        """Test outline creation workflow from UI"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # User clicks "AI Generate Outline"
        generate_data = {
            "project_id": project_id,
            "synopsis": sample_project_data["synopsis"],
            "chapter_count": 5
        }
        generate_response = await client.post("/api/outlines/generate", json=generate_data)

        # If generation succeeds, verify outlines created
        if generate_response.status_code == 200:
            outlines = generate_response.json()
            assert len(outlines) > 0

            # Refresh outline tree
            tree_response = await client.get(f"/api/outlines/project/{project_id}/tree")
            assert tree_response.status_code == 200
            tree = tree_response.json()
            assert len(tree) > 0

    async def test_chapter_creation_workflow(self, client: AsyncClient, sample_project_data):
        """Test chapter creation and generation workflow"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create outline
        outline_data = {
            "project_id": project_id,
            "title": "第一章大纲",
            "content": "章节规划内容"
        }
        outline_response = await client.post("/api/outlines", json=outline_data)
        outline_id = outline_response.json()["id"]

        # User clicks "Create Chapter" from outline
        chapter_data = {
            "project_id": project_id,
            "outline_id": outline_id,
            "title": "第一章",
            "chapter_number": 1
        }
        chapter_response = await client.post("/api/writing/chapters", json=chapter_data)
        assert chapter_response.status_code == 200
        chapter_id = chapter_response.json()["id"]

        # Verify chapter appears in list
        chapters_response = await client.get(f"/api/writing/chapters/project/{project_id}")
        assert chapters_response.status_code == 200
        chapters = chapters_response.json()
        assert any(c["id"] == chapter_id for c in chapters)

    async def test_character_management_workflow(self, client: AsyncClient, sample_project_data):
        """Test character creation and relationship workflow"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create multiple characters
        characters = []
        for i, name in enumerate(["主角", "配角", "反派"]):
            char_data = {
                "project_id": project_id,
                "name": name,
                "description": f"{name}描述",
                "status": "alive"
            }
            char_response = await client.post("/api/characters", json=char_data)
            assert char_response.status_code == 200
            characters.append(char_response.json())

        # Verify all characters in list
        list_response = await client.get(f"/api/characters/project/{project_id}")
        assert list_response.status_code == 200
        char_list = list_response.json()
        assert len(char_list) == 3

        # Try to create relationship (may fail if Neo4j not available)
        if len(characters) >= 2:
            rel_data = {
                "project_id": project_id,
                "source_id": characters[0]["id"],
                "target_id": characters[1]["id"],
                "relation_type": "FRIEND",
                "description": "好友"
            }
            rel_response = await client.post("/api/characters/relationships", json=rel_data)
            # Accept both success and failure
            assert rel_response.status_code in [200, 500]

    async def test_multi_project_isolation(self, client: AsyncClient, sample_project_data):
        """Test that data is properly isolated between projects"""
        # Create two projects
        project1_response = await client.post("/api/projects", json=sample_project_data)
        project1_id = project1_response.json()["id"]

        project2_data = {**sample_project_data, "title": "项目2"}
        project2_response = await client.post("/api/projects", json=project2_data)
        project2_id = project2_response.json()["id"]

        # Create outline in project 1
        outline1_data = {
            "project_id": project1_id,
            "title": "项目1大纲"
        }
        await client.post("/api/outlines", json=outline1_data)

        # Create character in project 2
        char2_data = {
            "project_id": project2_id,
            "name": "项目2角色"
        }
        await client.post("/api/characters", json=char2_data)

        # Verify project 1 has outline but no characters
        outlines1 = await client.get(f"/api/outlines/project/{project1_id}")
        chars1 = await client.get(f"/api/characters/project/{project1_id}")
        assert len(outlines1.json()) == 1
        assert len(chars1.json()) == 0

        # Verify project 2 has character but no outlines
        outlines2 = await client.get(f"/api/outlines/project/{project2_id}")
        chars2 = await client.get(f"/api/characters/project/{project2_id}")
        assert len(outlines2.json()) == 0
        assert len(chars2.json()) == 1

    async def test_error_handling_workflow(self, client: AsyncClient):
        """Test error handling for common scenarios"""
        # Try to get non-existent project
        response = await client.get("/api/projects/non-existent-id")
        assert response.status_code == 404

        # Try to create chapter without project
        chapter_data = {
            "project_id": "non-existent-id",
            "title": "章节"
        }
        response = await client.post("/api/writing/chapters", json=chapter_data)
        assert response.status_code in [404, 500]

        # Try to update non-existent character
        response = await client.put("/api/characters/non-existent-id", json={"name": "新名字"})
        assert response.status_code == 404

        # Try to delete non-existent outline
        response = await client.delete("/api/outlines/non-existent-id")
        assert response.status_code == 404
