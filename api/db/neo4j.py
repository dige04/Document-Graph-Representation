"""Neo4j client for FastAPI backend."""
import os
from neo4j import GraphDatabase
from neo4j.time import DateTime, Date, Time, Duration
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load .env from project root (try multiple locations for flexibility)
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))  # api/db -> project root
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))  # fallback


def _serialize_neo4j_value(value: Any) -> Any:
    """Convert Neo4j types to JSON-serializable Python types."""
    if isinstance(value, (DateTime, Date, Time)):
        return value.iso_format()
    elif isinstance(value, Duration):
        return str(value)
    elif isinstance(value, dict):
        return {k: _serialize_neo4j_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_serialize_neo4j_value(v) for v in value]
    return value


def _serialize_properties(props: Dict) -> Dict:
    """Serialize all properties in a dict to JSON-compatible values."""
    return {k: _serialize_neo4j_value(v) for k, v in props.items()}


class Neo4jClient:
    """Neo4j database client wrapper."""

    def __init__(self):
        uri = os.getenv('NEO4J_URI')
        username = os.getenv('NEO4J_USERNAME', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD') or os.getenv('NEO4J_AUTH')

        if not uri or not password:
            raise ValueError("NEO4J_URI and NEO4J_PASSWORD (or NEO4J_AUTH) must be set in environment")

        self.driver = GraphDatabase.driver(uri, auth=(username, password), keep_alive=True)

    def close(self):
        """Close the driver connection."""
        self.driver.close()

    def verify_connectivity(self) -> bool:
        """Verify Neo4j connection is working."""
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            return True
        except Exception:
            return False

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """Execute Cypher query and return results as list of dicts."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def get_test_rel_2_graph(self, limit: int = 100) -> Dict[str, List]:
        """
        Get Test_rel_2 nodes and relationships.
        Returns data in react-force-graph compatible format.
        Uses UNION to get diverse relationship types instead of just CONTAINS.
        """
        # Get diverse relationships by sampling from each type
        query = """
        // Get structural relationships (HAS_*)
        MATCH (n:Test_rel_2)-[r:HAS_CHAPTER|HAS_CLAUSE|HAS_POINT|HAS_SUBPOINT]-(m:Test_rel_2)
        RETURN n, r, m
        LIMIT $struct_limit
        UNION ALL
        // Get semantic relationships (Pursuant, Reference, Amended, Guide, Others)
        MATCH (n:Test_rel_2)-[r:Pursuant|Reference|Amended|Guide|Others]-(m:Test_rel_2)
        RETURN n, r, m
        LIMIT $semantic_limit
        UNION ALL
        // Get CONTAINS relationships
        MATCH (n:Test_rel_2)-[r:CONTAINS]-(m:Test_rel_2)
        RETURN n, r, m
        LIMIT $contains_limit
        """
        # Distribute limit: 40% structural, 30% semantic, 30% contains
        struct_limit = max(10, int(limit * 0.4))
        semantic_limit = max(10, int(limit * 0.3))
        contains_limit = max(10, int(limit * 0.3))

        with self.driver.session() as session:
            result = session.run(query, {
                "struct_limit": struct_limit,
                "semantic_limit": semantic_limit,
                "contains_limit": contains_limit
            })

            nodes_dict = {}
            links = []

            for record in result:
                # Process source node
                n = record['n']
                n_id = n.element_id
                if n_id not in nodes_dict:
                    # Determine label - prefer 'text' then 'id' then 'name'
                    label = n.get('text', n.get('id', n.get('name', 'Unknown')))

                    nodes_dict[n_id] = {
                        "id": n_id,
                        "label": str(label),
                        "type": self._infer_node_type(n),
                        "properties": _serialize_properties(dict(n))
                    }

                # Process target node
                m = record['m']
                m_id = m.element_id
                if m_id not in nodes_dict:
                    label = m.get('text', m.get('id', m.get('name', 'Unknown')))

                    nodes_dict[m_id] = {
                        "id": m_id,
                        "label": str(label),
                        "type": self._infer_node_type(m),
                        "properties": _serialize_properties(dict(m))
                    }

                # Process relationship
                r = record['r']
                links.append({
                    "source": n_id,
                    "target": m_id,
                    "type": r.type,
                    "properties": _serialize_properties(dict(r)) if r else {}
                })

            return {
                "nodes": list(nodes_dict.values()),
                "links": links
            }

    def _infer_node_type(self, node) -> str:
        """Infer node type from properties or labels."""
        # Check if node has specific type indicators
        props = dict(node)

        if 'type' in props:
            return props['type']
        if 'article' in str(props.get('id', '')).lower():
            return 'article'
        if props.get('embedding') or props.get('original_embedding'):
            return 'document'

        return 'document'

    def get_graph_schema(self) -> Dict[str, List]:
        """Get Test_rel_2 namespace schema - labels and relationship types."""
        # Get node labels
        labels_query = """
        MATCH (n:Test_rel_2)
        RETURN DISTINCT labels(n) as labels
        LIMIT 100
        """
        labels = self.execute_query(labels_query)

        # Get relationship types
        rels_query = """
        MATCH (n:Test_rel_2)-[r]-(m:Test_rel_2)
        RETURN DISTINCT type(r) as relType
        """
        rels = self.execute_query(rels_query)

        # Get property keys
        props_query = """
        MATCH (n:Test_rel_2)
        RETURN DISTINCT keys(n) as props
        LIMIT 10
        """
        props = self.execute_query(props_query)

        return {
            "labels": [l['labels'] for l in labels],
            "relationships": [r['relType'] for r in rels],
            "properties": list(set(p for row in props for p in row.get('props', [])))
        }

    def get_node_count(self, namespace: str = "Test_rel_2") -> int:
        """Get total node count for namespace."""
        query = f"MATCH (n:{namespace}) RETURN count(n) as count"
        result = self.execute_query(query)
        return result[0]['count'] if result else 0


# Singleton instance - lazy initialization
_neo4j_client = None


def get_neo4j_client() -> Neo4jClient:
    """Get or create Neo4j client singleton."""
    global _neo4j_client
    if _neo4j_client is None:
        _neo4j_client = Neo4jClient()
    return _neo4j_client


def reset_neo4j_client():
    """Reset the Neo4j client singleton (useful after env changes)."""
    global _neo4j_client
    if _neo4j_client is not None:
        try:
            _neo4j_client.close()
        except Exception:
            pass
    _neo4j_client = None


def is_neo4j_available() -> bool:
    """Check if Neo4j is available without raising exceptions."""
    try:
        client = get_neo4j_client()
        return client.verify_connectivity()
    except Exception:
        return False
