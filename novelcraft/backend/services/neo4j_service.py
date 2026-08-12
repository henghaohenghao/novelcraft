"""
Neo4j 图数据库服务

管理人物关系图谱、阵营、地点、事件等图数据的存储和查询，
为写作智能体提供人物关系和场景上下文。
"""
from neo4j import GraphDatabase, Driver
from backend.config import get_settings

settings = get_settings()


class Neo4jService:
    """Neo4j 图数据库客户端：人物关系图谱管理"""

    def __init__(self):
        self._driver: Driver | None = None
        self.available: bool = False

    @property
    def driver(self) -> Driver:
        """延迟连接 Neo4j 驱动"""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        return self._driver

    def close(self):
        """关闭 Neo4j 连接"""
        if self._driver:
            self._driver.close()
            self._driver = None
        self.available = False

    def init_constraints(self):
        """初始化唯一性约束：Character、Faction、Location、Event 的 id 约束"""
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (c:Character) REQUIRE c.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (f:Faction) REQUIRE f.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE")
        self.available = True

    def create_character(self, project_id: str, char_data: dict):
        """在图中创建人物节点"""
        if not self.available:
            return None
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (c:Character {
                    id: $id, project_id: $project_id, name: $name,
                    alias: $alias, description: $description,
                    personality: $personality, background: $background,
                    appearance: $appearance, abilities: $abilities, status: $status
                })
                RETURN c
                """,
                id=char_data["id"],
                project_id=project_id,
                name=char_data["name"],
                alias=char_data.get("alias", ""),
                description=char_data.get("description", ""),
                personality=char_data.get("personality", ""),
                background=char_data.get("background", ""),
                appearance=char_data.get("appearance", ""),
                abilities=char_data.get("abilities", ""),
                status=char_data.get("status", "alive"),
            )
            return result.single()

    def update_character(self, char_id: str, char_data: dict):
        """更新图中人物节点的属性"""
        if not self.available:
            return None
        with self.driver.session() as session:
            set_clauses = []
            params = {"id": char_id}
            for key, value in char_data.items():
                if value is not None:
                    set_clauses.append(f"c.{key} = ${key}")
                    params[key] = value
            if not set_clauses:
                return None
            query = f"MATCH (c:Character {{id: $id}}) SET {', '.join(set_clauses)} RETURN c"
            result = session.run(query, **params)
            return result.single()

    def delete_character(self, char_id: str):
        """删除图中人物节点及其所有关系"""
        if not self.available:
            return None
        with self.driver.session() as session:
            session.run("MATCH (c:Character {id: $id}) DETACH DELETE c", id=char_id)

    def create_relationship(self, source_id: str, target_id: str, rel_type: str, description: str = ""):
        """创建两个节点之间的关系"""
        if not self.available:
            return None
        valid_types = {"RELATIVE", "ENEMY", "MENTOR", "FRIEND", "LOVER", "COLLEAGUE", "RIVAL", "SUBORDINATE", "MASTER", "ALLY"}
        if rel_type.upper() not in valid_types:
            rel_type = "ALLY"

        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (a {{id: $source_id}}), (b {{id: $target_id}})
                MERGE (a)-[r:{rel_type.upper()} {{description: $description}}]->(b)
                RETURN a, r, b
                """,
                source_id=source_id,
                target_id=target_id,
                description=description,
            )
            return result.single()

    def delete_relationship(self, source_id: str, target_id: str, rel_type: str):
        """删除节点间的关系"""
        if not self.available:
            return None
        with self.driver.session() as session:
            session.run(
                f"""
                MATCH (a {{id: $source_id}})-[r:{rel_type.upper()}]->(b {{id: $target_id}})
                DELETE r
                """,
                source_id=source_id,
                target_id=target_id,
            )

    def get_character_relations(self, char_id: str) -> list[dict]:
        """查询人物的所有关系"""
        if not self.available:
            return []
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c {id: $id})-[r]-(other)
                RETURN c.name AS source_name, type(r) AS relation_type,
                       r.description AS description, other.name AS target_name,
                       other.id AS target_id, labels(other) AS target_labels
                """,
                id=char_id,
            )
            relations = []
            for record in result:
                relations.append({
                    "source_name": record["source_name"],
                    "relation_type": record["relation_type"],
                    "description": record["description"],
                    "target_name": record["target_name"],
                    "target_id": record["target_id"],
                    "target_labels": record["target_labels"],
                })
            return relations

    def get_project_graph(self, project_id: str) -> dict:
        """获取项目完整图谱：所有节点和关系"""
        if not self.available:
            return {"nodes": [], "edges": []}
        with self.driver.session() as session:
            nodes_result = session.run(
                """
                MATCH (n)
                WHERE n.project_id = $project_id
                RETURN n.id AS id, n.name AS name, labels(n) AS labels
                """,
                project_id=project_id,
            )
            nodes = []
            for record in nodes_result:
                nodes.append({
                    "id": record["id"],
                    "name": record["name"],
                    "labels": record["labels"],
                })

            edges_result = session.run(
                """
                MATCH (a)-[r]-(b)
                WHERE a.project_id = $project_id AND b.project_id = $project_id
                RETURN a.id AS source, b.id AS target, type(r) AS relation_type,
                       r.description AS description
                """,
                project_id=project_id,
            )
            edges = []
            for record in edges_result:
                edges.append({
                    "source": record["source"],
                    "target": record["target"],
                    "relation_type": record["relation_type"],
                    "description": record["description"],
                })

            return {"nodes": nodes, "edges": edges}

    def get_scene_context(self, project_id: str, character_names: list[str]) -> dict:
        """获取场景上下文：指定人物的关系网"""
        if not self.available:
            return {"characters": []}
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Character)
                WHERE c.project_id = $project_id AND c.name IN $names
                OPTIONAL MATCH (c)-[r]-(other)
                WHERE other.project_id = $project_id
                RETURN c, collect(DISTINCT {type: type(r), target: other.name,
                       target_type: labels(other)[0], desc: r.description}) AS relations
                """,
                project_id=project_id,
                names=character_names,
            )
            characters = []
            for record in result:
                char_node = record["c"]
                characters.append({
                    "name": char_node["name"],
                    "description": char_node.get("description", ""),
                    "personality": char_node.get("personality", ""),
                    "status": char_node.get("status", ""),
                    "relations": record["relations"],
                })
            return {"characters": characters}

    def create_faction(self, project_id: str, faction_data: dict):
        """在图中创建阵营节点"""
        if not self.available:
            return None
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (f:Faction {
                    id: $id, project_id: $project_id, name: $name,
                    description: $description, goal: $goal
                })
                RETURN f
                """,
                id=faction_data["id"],
                project_id=project_id,
                name=faction_data["name"],
                description=faction_data.get("description", ""),
                goal=faction_data.get("goal", ""),
            )
            return result.single()

    def create_location(self, project_id: str, location_data: dict):
        """在图中创建地点节点"""
        if not self.available:
            return None
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (l:Location {
                    id: $id, project_id: $project_id, name: $name,
                    description: $description, location_type: $location_type
                })
                RETURN l
                """,
                id=location_data["id"],
                project_id=project_id,
                name=location_data["name"],
                description=location_data.get("description", ""),
                location_type=location_data.get("location_type", "general"),
            )
            return result.single()

    def create_event(self, project_id: str, event_data: dict):
        """在图中创建事件节点"""
        if not self.available:
            return None
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (e:Event {
                    id: $id, project_id: $project_id, name: $name,
                    description: $description, event_time: $event_time,
                    chapter_id: $chapter_id
                })
                RETURN e
                """,
                id=event_data["id"],
                project_id=project_id,
                name=event_data["name"],
                description=event_data.get("description", ""),
                event_time=event_data.get("event_time", ""),
                chapter_id=event_data.get("chapter_id", ""),
            )
            return result.single()


neo4j_service = Neo4jService()
