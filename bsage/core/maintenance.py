"""Built-in maintenance tasks — core scheduled jobs that must always run.

These are NOT plugins. They are infrastructure tasks that the system
depends on for correctness (maturity promotion/demotion, edge lifecycle,
ontology evolution). They run on fixed cron schedules via the Scheduler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from bsage.garden.graph_store import GraphStore
    from bsage.garden.ontology import OntologyRegistry
    from bsage.garden.writer import GardenWriter

logger = structlog.get_logger(__name__)

# Schedule definitions: (name, cron, description)
MAINTENANCE_SCHEDULES: list[tuple[str, str]] = [
    ("maintenance:maturity", "0 6 * * *"),
    ("maintenance:edge-lifecycle", "0 4 * * *"),
    ("maintenance:ontology-evolution", "0 3 * * *"),
]


class MaintenanceTasks:
    """Core maintenance tasks that run on fixed schedules.

    Unlike plugins, these have direct access to internal modules
    and are guaranteed to run as long as the scheduler is active.
    """

    def __init__(
        self,
        garden_writer: GardenWriter,
        graph_store: GraphStore | None = None,
        ontology: OntologyRegistry | None = None,
    ) -> None:
        self._garden = garden_writer
        self._graph = graph_store
        self._ontology = ontology

    async def run_maturity(self) -> dict[str, Any]:
        """Evaluate and promote/demote garden note maturity."""
        result = await self._garden.promote_maturity(self._graph)
        if result["promoted"] > 0:
            details = ", ".join(f"{d['path']} ({d['from']}→{d['to']})" for d in result["details"])
            await self._garden.write_action(
                "maintenance:maturity",
                f"Promoted {result['promoted']} notes: {details}",
            )
        logger.info(
            "maintenance_maturity_done",
            promoted=result["promoted"],
            checked=result["checked"],
        )
        return result

    async def run_edge_lifecycle(self) -> dict[str, Any]:
        """Promote frequently-mentioned weak edges; demote stale strong edges."""
        if self._graph is None:
            return {"status": "skipped", "reason": "no graph"}

        from bsage.garden.edge_lifecycle import EdgeLifecycleConfig, EdgeLifecycleEvaluator

        evaluator = EdgeLifecycleEvaluator(self._graph, EdgeLifecycleConfig())
        promoted = await evaluator.promote_edges()
        demoted = await evaluator.demote_edges()

        if promoted or demoted:
            await self._garden.write_action(
                "maintenance:edge-lifecycle",
                f"Promoted {promoted} edges, demoted {demoted} edges",
            )
        logger.info(
            "maintenance_edge_lifecycle_done",
            promoted=promoted,
            demoted=demoted,
        )
        return {"promoted": promoted, "demoted": demoted}

    async def run_ontology_evolution(self) -> dict[str, Any]:
        """Review ontology for DEPRECATE candidates (zero-activity types)."""
        if self._ontology is None or self._graph is None:
            return {"status": "skipped", "reason": "no ontology or graph"}

        entity_types = self._ontology.get_entity_types()
        candidates = []

        for type_name, type_info in entity_types.items():
            if not type_info.get("folder"):
                continue
            count = await self._graph.count_relationships_for_entity(type_name)
            if count == 0:
                candidates.append(type_name)

        deprecated = 0
        for type_name in candidates:
            result = await self._ontology.deprecate_entity_type(
                type_name, reason="no relationships found"
            )
            if result:
                deprecated += 1

        if deprecated or candidates:
            await self._garden.write_action(
                "maintenance:ontology-evolution",
                f"Reviewed {len(candidates)} candidates, deprecated {deprecated} types",
            )
        logger.info(
            "maintenance_ontology_evolution_done",
            candidates=len(candidates),
            deprecated=deprecated,
        )
        return {"candidates": len(candidates), "deprecated": deprecated}
