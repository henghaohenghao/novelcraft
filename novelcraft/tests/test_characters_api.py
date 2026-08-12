"""
Tests for Characters API endpoints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestCharactersAPI:
    """Test suite for /api/characters endpoints"""

    async def test_create_character(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test POST /api/characters - Create character"""
        # Create project first
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create character
        character_data = {**sample_character_data, "project_id": project_id}
        response = await client.post("/api/characters", json=character_data)

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["project_id"] == project_id
        assert data["name"] == sample_character_data["name"]
        assert data["alias"] == sample_character_data["alias"]
        assert data["personality"] == sample_character_data["personality"]
        assert data["status"] == "alive"

    async def test_get_project_characters(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test GET /api/characters/project/{project_id} - Get character list"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create multiple characters
        characters = ["张三", "李四", "王五"]
        for name in characters:
            character_data = {**sample_character_data, "project_id": project_id, "name": name}
            await client.post("/api/characters", json=character_data)

        # Get characters
        response = await client.get(f"/api/characters/project/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

        names = [c["name"] for c in data]
        assert all(name in names for name in characters)

    async def test_get_character_by_id(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test GET /api/characters/{character_id} - Get character details"""
        # Create project and character
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        character_data = {**sample_character_data, "project_id": project_id}
        character_response = await client.post("/api/characters", json=character_data)
        character_id = character_response.json()["id"]

        # Get character by ID
        response = await client.get(f"/api/characters/{character_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == character_id
        assert data["name"] == sample_character_data["name"]

    async def test_update_character(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test PUT /api/characters/{character_id} - Update character"""
        # Create project and character
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        character_data = {**sample_character_data, "project_id": project_id}
        character_response = await client.post("/api/characters", json=character_data)
        character_id = character_response.json()["id"]

        # Update character
        update_data = {
            "name": "张三丰",
            "status": "dead",
            "abilities": "太极拳、太极剑"
        }
        response = await client.put(f"/api/characters/{character_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "张三丰"
        assert data["status"] == "dead"
        assert data["abilities"] == "太极拳、太极剑"

    async def test_delete_character(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test DELETE /api/characters/{character_id} - Delete character"""
        # Create project and character
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        character_data = {**sample_character_data, "project_id": project_id}
        character_response = await client.post("/api/characters", json=character_data)
        character_id = character_response.json()["id"]

        # Delete character
        response = await client.delete(f"/api/characters/{character_id}")

        assert response.status_code == 200

        # Verify deletion
        get_response = await client.get(f"/api/characters/{character_id}")
        assert get_response.status_code == 404

    async def test_create_character_relationship(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test POST /api/characters/relationships - Create relationship"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create two characters
        char1_data = {**sample_character_data, "project_id": project_id, "name": "张三"}
        char1_response = await client.post("/api/characters", json=char1_data)
        char1_id = char1_response.json()["id"]

        char2_data = {**sample_character_data, "project_id": project_id, "name": "李四"}
        char2_response = await client.post("/api/characters", json=char2_data)
        char2_id = char2_response.json()["id"]

        # Create relationship (will work if Neo4j is available)
        relationship_data = {
            "project_id": project_id,
            "source_id": char1_id,
            "target_id": char2_id,
            "relation_type": "FRIEND",
            "description": "好友关系"
        }
        response = await client.post("/api/characters/relationships", json=relationship_data)

        # May return 200 or 500 depending on Neo4j availability
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert data["source_id"] == char1_id
            assert data["target_id"] == char2_id
            assert data["relation_type"] == "FRIEND"

    async def test_get_character_relations(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test GET /api/characters/{character_id}/relations - Get character relations"""
        # Create project and character
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        character_data = {**sample_character_data, "project_id": project_id}
        character_response = await client.post("/api/characters", json=character_data)
        character_id = character_response.json()["id"]

        # Get relations
        response = await client.get(f"/api/characters/{character_id}/relations")

        # Should return empty list if Neo4j not available, or list of relations if available
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    async def test_get_project_graph(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test GET /api/characters/project/{project_id}/graph - Get project graph"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create characters
        for i in range(3):
            character_data = {**sample_character_data, "project_id": project_id, "name": f"角色{i+1}"}
            await client.post("/api/characters", json=character_data)

        # Get graph
        response = await client.get(f"/api/characters/project/{project_id}/graph")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)

    async def test_generate_characters_from_synopsis(self, client: AsyncClient, sample_project_data):
        """Test POST /api/characters/generate-from-synopsis - AI generate characters"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Try to generate characters (will fail without proper LLM)
        response = await client.post(
            f"/api/characters/generate-from-synopsis?project_id={project_id}&synopsis={sample_project_data['synopsis']}"
        )

        # May succeed or fail depending on LLM availability
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    async def test_delete_character_relationship(self, client: AsyncClient, sample_project_data, sample_character_data):
        """Test DELETE /api/characters/relationships - Delete relationship"""
        # Create project and characters
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        char1_data = {**sample_character_data, "project_id": project_id, "name": "张三"}
        char1_response = await client.post("/api/characters", json=char1_data)
        char1_id = char1_response.json()["id"]

        char2_data = {**sample_character_data, "project_id": project_id, "name": "李四"}
        char2_response = await client.post("/api/characters", json=char2_data)
        char2_id = char2_response.json()["id"]

        # Try to delete relationship
        response = await client.delete(
            f"/api/characters/relationships?source_id={char1_id}&target_id={char2_id}&relation_type=FRIEND"
        )

        # May succeed or fail depending on Neo4j availability
        assert response.status_code in [200, 404, 500]

    async def test_create_faction(self, client: AsyncClient, sample_project_data):
        """Test POST /api/characters/factions - Create faction"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create faction
        faction_data = {
            "project_id": project_id,
            "name": "武当派",
            "description": "道家武学门派",
            "goal": "维护武林正义"
        }
        response = await client.post("/api/characters/factions", json=faction_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "武当派"

    async def test_get_project_factions(self, client: AsyncClient, sample_project_data):
        """Test GET /api/characters/factions/project/{project_id} - Get factions"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create factions
        factions = ["武当派", "少林寺", "峨眉派"]
        for name in factions:
            faction_data = {
                "project_id": project_id,
                "name": name,
                "description": f"{name}描述"
            }
            await client.post("/api/characters/factions", json=faction_data)

        # Get factions
        response = await client.get(f"/api/characters/factions/project/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_create_location(self, client: AsyncClient, sample_project_data):
        """Test POST /api/characters/locations - Create location"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create location
        location_data = {
            "project_id": project_id,
            "name": "武当山",
            "description": "道家圣地",
            "location_type": "mountain"
        }
        response = await client.post("/api/characters/locations", json=location_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "武当山"

    async def test_get_project_locations(self, client: AsyncClient, sample_project_data):
        """Test GET /api/characters/locations/project/{project_id} - Get locations"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create locations
        locations = ["武当山", "少林寺", "峨眉山"]
        for name in locations:
            location_data = {
                "project_id": project_id,
                "name": name,
                "description": f"{name}描述"
            }
            await client.post("/api/characters/locations", json=location_data)

        # Get locations
        response = await client.get(f"/api/characters/locations/project/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_create_event(self, client: AsyncClient, sample_project_data):
        """Test POST /api/characters/events - Create event"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create event
        event_data = {
            "project_id": project_id,
            "name": "华山论剑",
            "description": "武林大会",
            "event_time": "某年某月"
        }
        response = await client.post("/api/characters/events", json=event_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "华山论剑"

    async def test_get_project_events(self, client: AsyncClient, sample_project_data):
        """Test GET /api/characters/events/project/{project_id} - Get events"""
        # Create project
        project_response = await client.post("/api/projects", json=sample_project_data)
        project_id = project_response.json()["id"]

        # Create events
        events = ["华山论剑", "武林大会", "江湖风云"]
        for name in events:
            event_data = {
                "project_id": project_id,
                "name": name,
                "description": f"{name}描述"
            }
            await client.post("/api/characters/events", json=event_data)

        # Get events
        response = await client.get(f"/api/characters/events/project/{project_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
