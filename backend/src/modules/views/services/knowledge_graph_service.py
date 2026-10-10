"""
Knowledge Graph Service - Relationship and entity graph management

This service provides:
- Relationship edge management
- Connection path finding
- Relevant context graph extraction
- Entity relationship queries

Extracted from assistant/services/knowledge_graph_service.py.
"""

from typing import Optional, Dict, Any, List, Set, Tuple
from uuid import UUID
from collections import deque

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ...member.models.person_profile import PersonProfile, ProfileStatus
from ...member.models.relationship import RelationshipEdge

logger = get_logger(__name__)


class KnowledgeGraphService:
    """Service for managing the knowledge graph of person relationships."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_or_update_edge(
        self,
        user_id: UUID,
        family_id: UUID,
        person_a_id: UUID,
        person_b_id: UUID,
        relationship_type: str,
        context: Optional[str] = None,
        strength: float = 0.5,
        bidirectional: bool = True,
        source_memory_id: Optional[UUID] = None,
    ) -> RelationshipEdge:
        """
        Create or update a relationship edge between two persons.

        If an edge already exists, strengthens it and adds the source memory.

        Args:
            user_id: The user ID
            family_id: The family ID
            person_a_id: First person profile ID
            person_b_id: Second person profile ID
            relationship_type: Type of relationship
            context: Context/description of relationship
            strength: Initial strength (0-1)
            bidirectional: Whether relationship is bidirectional
            source_memory_id: ID of memory that established this relationship

        Returns:
            The created or updated edge
        """
        # Check for existing edge (in either direction for bidirectional)
        existing = await self._find_existing_edge(
            user_id, person_a_id, person_b_id, bidirectional
        )

        if existing:
            # Strengthen existing relationship
            existing.strengthen(0.1)
            if source_memory_id:
                existing.add_source_memory(source_memory_id)
            if context and not existing.context:
                existing.context = context
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        # Create new edge
        edge = RelationshipEdge(
            user_id=user_id,
            family_id=family_id,
            person_a_id=person_a_id,
            person_b_id=person_b_id,
            relationship_type=relationship_type,
            strength=strength,
            context=context,
            bidirectional=bidirectional,
            source_memory_ids=[source_memory_id] if source_memory_id else [],
        )
        self.db.add(edge)
        await self.db.commit()
        await self.db.refresh(edge)

        return edge

    async def _find_existing_edge(
        self,
        user_id: UUID,
        person_a_id: UUID,
        person_b_id: UUID,
        check_reverse: bool = True,
    ) -> Optional[RelationshipEdge]:
        """Find an existing edge between two persons."""
        conditions = [
            RelationshipEdge.user_id == user_id,
            or_(
                and_(
                    RelationshipEdge.person_a_id == person_a_id,
                    RelationshipEdge.person_b_id == person_b_id,
                ),
                and_(
                    RelationshipEdge.person_a_id == person_b_id,
                    RelationshipEdge.person_b_id == person_a_id,
                ) if check_reverse else False,
            ),
        ]

        query = select(RelationshipEdge).where(and_(*conditions)).limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_connections(
        self,
        user_id: UUID,
        person_id: UUID,
        min_strength: float = 0.0,
    ) -> List[Tuple[PersonProfile, RelationshipEdge]]:
        """
        Get all connections for a person.

        Args:
            user_id: The user ID
            person_id: The person profile ID
            min_strength: Minimum relationship strength to include

        Returns:
            List of (connected_person, edge) tuples
        """
        # Get all edges involving this person
        query = select(RelationshipEdge).where(
            and_(
                RelationshipEdge.user_id == user_id,
                RelationshipEdge.strength >= min_strength,
                or_(
                    RelationshipEdge.person_a_id == person_id,
                    RelationshipEdge.person_b_id == person_id,
                ),
            )
        ).order_by(RelationshipEdge.strength.desc())

        result = await self.db.execute(query)
        edges = list(result.scalars().all())

        if not edges:
            return []

        # Collect all other person IDs to batch load profiles
        other_ids = set()
        for edge in edges:
            other_id = edge.get_other_person_id(person_id)
            if other_id:
                other_ids.add(other_id)

        if not other_ids:
            return []

        # Batch load all profiles in one query (fixes N+1 problem)
        profiles_query = select(PersonProfile).where(PersonProfile.id.in_(other_ids))
        profiles_result = await self.db.execute(profiles_query)
        profiles_by_id = {p.id: p for p in profiles_result.scalars().all()}

        # Build result
        connections = []
        for edge in edges:
            other_id = edge.get_other_person_id(person_id)
            if other_id and other_id in profiles_by_id:
                connections.append((profiles_by_id[other_id], edge))

        return connections

    async def _get_person_profile(self, profile_id: UUID) -> Optional[PersonProfile]:
        """Get a person profile by ID."""
        query = select(PersonProfile).where(PersonProfile.id == profile_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def find_connection_path(
        self,
        user_id: UUID,
        person_a_id: UUID,
        person_b_id: UUID,
        max_depth: int = 3,
    ) -> Optional[List[Tuple[PersonProfile, RelationshipEdge]]]:
        """
        Find a connection path between two persons using BFS.

        Args:
            user_id: The user ID
            person_a_id: Starting person ID
            person_b_id: Target person ID
            max_depth: Maximum path depth to search

        Returns:
            List of (person, edge) tuples representing the path, or None if no path
        """
        if person_a_id == person_b_id:
            return []

        # BFS to find shortest path
        visited: Set[UUID] = {person_a_id}
        queue: deque = deque([(person_a_id, [])])

        while queue:
            current_id, path = queue.popleft()

            if len(path) >= max_depth:
                continue

            # Get connections for current person
            connections = await self.get_connections(user_id, current_id)

            for connected_person, edge in connections:
                if connected_person.id in visited:
                    continue

                new_path = path + [(connected_person, edge)]

                if connected_person.id == person_b_id:
                    return new_path

                visited.add(connected_person.id)
                queue.append((connected_person.id, new_path))

        return None  # No path found

    async def get_relevant_context_graph(
        self,
        user_id: UUID,
        person_ids: List[UUID],
        depth: int = 1,
    ) -> Dict[str, Any]:
        """
        Get a subgraph of relevant context for given persons.

        Args:
            user_id: The user ID
            person_ids: List of person IDs to include
            depth: How many levels of connections to include

        Returns:
            Graph structure with nodes (persons) and edges (relationships)
        """
        nodes: Dict[UUID, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        to_process = set(person_ids)
        processed: Set[UUID] = set()

        for _ in range(depth + 1):
            # Filter out already processed IDs
            ids_to_load = to_process - processed
            if not ids_to_load:
                break

            # Batch load all profiles for this level (fixes N+1 query)
            profiles_query = select(PersonProfile).where(PersonProfile.id.in_(ids_to_load))
            profiles_result = await self.db.execute(profiles_query)
            profiles_by_id = {p.id: p for p in profiles_result.scalars().all()}

            new_to_process: Set[UUID] = set()

            for person_id in ids_to_load:
                processed.add(person_id)

                # Use batch-loaded profile
                profile = profiles_by_id.get(person_id)
                if profile:
                    nodes[person_id] = {
                        "id": str(person_id),
                        "name": profile.name,
                        "relationship": profile.relationship,
                        "location": profile.location,
                    }

                # Get connections (already optimized with batch loading)
                connections = await self.get_connections(user_id, person_id)
                for connected_person, edge in connections:
                    # Add edge if not already added
                    edge_key = tuple(sorted([str(person_id), str(connected_person.id)]))
                    edge_exists = any(
                        tuple(sorted([e["source"], e["target"]])) == edge_key
                        for e in edges
                    )
                    if not edge_exists:
                        edges.append({
                            "source": str(person_id),
                            "target": str(connected_person.id),
                            "type": edge.relationship_type,
                            "strength": edge.strength,
                            "context": edge.context,
                        })

                    # Add to next level processing
                    if connected_person.id not in processed:
                        new_to_process.add(connected_person.id)

            to_process = new_to_process

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
        }

    async def get_mutual_connections(
        self,
        user_id: UUID,
        person_a_id: UUID,
        person_b_id: UUID,
    ) -> List[PersonProfile]:
        """
        Find mutual connections between two persons.

        Args:
            user_id: The user ID
            person_a_id: First person ID
            person_b_id: Second person ID

        Returns:
            List of persons connected to both
        """
        # Get connections for both persons
        connections_a = await self.get_connections(user_id, person_a_id)
        connections_b = await self.get_connections(user_id, person_b_id)

        ids_a = {p.id for p, _ in connections_a}
        ids_b = {p.id for p, _ in connections_b}

        mutual_ids = ids_a & ids_b

        # Get mutual profiles
        mutual = []
        for person_id in mutual_ids:
            profile = await self._get_person_profile(person_id)
            if profile:
                mutual.append(profile)

        return mutual

    async def get_network_summary(
        self,
        user_id: UUID,
        family_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get a summary of the user's relationship network.

        Returns:
            Summary with statistics and key insights
        """
        # Count persons
        person_count = await self.db.execute(
            select(func.count(PersonProfile.id)).where(
                and_(
                    PersonProfile.user_id == user_id,
                    PersonProfile.status == ProfileStatus.ACTIVE.value,
                )
            )
        )
        total_persons = person_count.scalar_one()

        # Count edges
        edge_count = await self.db.execute(
            select(func.count(RelationshipEdge.id)).where(
                RelationshipEdge.user_id == user_id
            )
        )
        total_edges = edge_count.scalar_one()

        # Get relationship type distribution
        type_query = select(
            RelationshipEdge.relationship_type,
            func.count(RelationshipEdge.id)
        ).where(
            RelationshipEdge.user_id == user_id
        ).group_by(RelationshipEdge.relationship_type)

        type_result = await self.db.execute(type_query)
        type_distribution = {row[0]: row[1] for row in type_result.all()}

        # Get most connected persons
        connected_query = select(
            RelationshipEdge.person_a_id,
            func.count(RelationshipEdge.id).label("count")
        ).where(
            RelationshipEdge.user_id == user_id
        ).group_by(
            RelationshipEdge.person_a_id
        ).order_by(
            func.count(RelationshipEdge.id).desc()
        ).limit(5)

        # This is a simplified query - in production you'd want to count both directions

        return {
            "total_persons": total_persons,
            "total_relationships": total_edges,
            "relationship_types": type_distribution,
            "network_density": (
                (2 * total_edges) / (total_persons * (total_persons - 1))
                if total_persons > 1 else 0
            ),
        }

    async def format_graph_for_llm(
        self,
        graph: Dict[str, Any],
        context_person: Optional[str] = None,
    ) -> str:
        """Format a graph for inclusion in LLM context."""
        if not graph.get("nodes"):
            return ""

        parts = ["\u3010\u76f8\u5173\u4eba\u7269\u5173\u7cfb\u3011"]

        if context_person:
            parts.append(f"\u4ee5\u4e0b\u662f\u4e0e{context_person}\u76f8\u5173\u7684\u4eba\u7269\u5173\u7cfb\uff1a\n")
        else:
            parts.append("\u4ee5\u4e0b\u662f\u76f8\u5173\u7684\u4eba\u7269\u5173\u7cfb\uff1a\n")

        # Format nodes
        for node in graph["nodes"]:
            desc_parts = [f"\u2022 {node['name']}"]
            if node.get("relationship"):
                desc_parts.append(f"\uff08{node['relationship']}\uff09")
            if node.get("location"):
                desc_parts.append(f"\uff0c\u5728{node['location']}")
            parts.append("".join(desc_parts))

        # Format edges
        if graph.get("edges"):
            parts.append("\n\u5173\u7cfb\uff1a")
            for edge in graph["edges"]:
                source_name = next(
                    (n["name"] for n in graph["nodes"] if n["id"] == edge["source"]),
                    edge["source"]
                )
                target_name = next(
                    (n["name"] for n in graph["nodes"] if n["id"] == edge["target"]),
                    edge["target"]
                )
                rel_type = edge.get("type", "\u8ba4\u8bc6")
                context = edge.get("context", "")

                line = f"  - {source_name} \u548c {target_name}\uff1a{rel_type}"
                if context:
                    line += f"\uff08{context}\uff09"
                parts.append(line)

        return "\n".join(parts)
