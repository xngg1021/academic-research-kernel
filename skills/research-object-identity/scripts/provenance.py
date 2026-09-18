# -*- coding: utf-8 -*-
"""Research Object Provenance Kernel & Lineage Receipt v1.

Deterministic, content-addressed scientific derivation and provenance kernel
grounded in W3C PROV-DM (Entity, Activity, used, generated, derived_from).

Core Capabilities:
1. First-class Entity & Activity dataclasses with content-addressing (SHA256).
2. LineageGraph: In-memory causal derivation graph container.
3. validate_lineage(): Strict topological DAG verification, referential
   integrity, and on-disk file hash checks.
4. trace_origin(): Millisecond-level deterministic backward traversal
   from any downstream artifact or table cell back to root input datasets,
   emitting standardized LineageReceipt records matching
   schemas/lineage-receipt.schema.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

__all__ = [
    "Entity",
    "Activity",
    "LineageEdge",
    "LineageGraph",
    "LineageReceipt",
    "validate_lineage",
    "trace_origin",
    "compute_file_sha256",
]


def compute_file_sha256(path: str | Path, chunk_size: int = 65536) -> str:
    """Compute content-addressed SHA256 digest of a local file in streaming blocks."""
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Cannot hash non-existent file: {p}")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


@dataclass
class Entity:
    id: str
    type: str  # data_snapshot, code_file, environment_spec, statistic_artifact, table_cell, figure_artifact, generic_entity
    sha256: Optional[str] = None
    locator: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"id": self.id, "type": self.type}
        if self.sha256:
            d["sha256"] = self.sha256.lower()
        if self.locator:
            d["locator"] = str(self.locator)
        if self.metadata:
            d["metadata"] = self.metadata
        return d


@dataclass
class Activity:
    id: str
    type: str  # data_cleaning, computation_run, statistical_analysis, table_extraction, render_run, generic_activity
    command: Optional[str] = None
    script_id: Optional[str] = None
    commit_sha: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"id": self.id, "type": self.type}
        if self.command:
            d["command"] = self.command
        if self.script_id:
            d["script_id"] = self.script_id
        if self.commit_sha:
            d["commit_sha"] = self.commit_sha
        if self.parameters:
            d["parameters"] = self.parameters
        if self.environment:
            d["environment"] = self.environment
        if self.timestamp:
            d["timestamp"] = self.timestamp
        return d


@dataclass
class LineageEdge:
    type: str  # used, generated, derived_from
    source_id: str
    target_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": self.type,
            "source_id": self.source_id,
            "target_id": self.target_id,
        }
        if self.metadata:
            d["metadata"] = self.metadata
        return d


class LineageGraph:
    """In-memory causal derivation graph container holding Entities, Activities, and Edges."""

    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.activities: Dict[str, Activity] = {}
        self.edges: List[LineageEdge] = []

    def add_entity(
        self,
        id: str,
        type: str,
        sha256: Optional[str] = None,
        locator: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Entity:
        ent = Entity(id=id, type=type, sha256=sha256, locator=locator, metadata=metadata or {})
        self.entities[id] = ent
        return ent

    def add_activity(
        self,
        id: str,
        type: str,
        command: Optional[str] = None,
        script_id: Optional[str] = None,
        commit_sha: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        environment: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> Activity:
        act = Activity(
            id=id,
            type=type,
            command=command,
            script_id=script_id,
            commit_sha=commit_sha,
            parameters=parameters or {},
            environment=environment or {},
            timestamp=timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self.activities[id] = act
        return act

    def record_used(self, activity_id: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Record that an Activity consumed an Entity as input."""
        self.edges.append(LineageEdge(type="used", source_id=activity_id, target_id=entity_id, metadata=metadata or {}))

    def record_generated(self, activity_id: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Record that an Activity generated an Entity as output."""
        self.edges.append(LineageEdge(type="generated", source_id=activity_id, target_id=entity_id, metadata=metadata or {}))

    def record_derivation(
        self,
        derived_entity_id: str,
        source_entity_id: str,
        activity_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record that derived_entity_id was derived from source_entity_id."""
        meta = dict(metadata or {})
        if activity_id:
            meta["activity_id"] = activity_id
        self.edges.append(LineageEdge(type="derived_from", source_id=derived_entity_id, target_id=source_entity_id, metadata=meta))


@dataclass
class LineageReceipt:
    protocol: str = "lineage-receipt-1.0"
    receipt_id: str = ""
    timestamp: str = ""
    target_id: str = ""
    verification_status: str = "intact"  # intact, broken_chain, hash_mismatch, missing_input, cycle_detected
    error_detail: Optional[str] = None
    root_ancestors: List[str] = field(default_factory=list)
    entities: List[Entity] = field(default_factory=list)
    activities: List[Activity] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)
    trace_steps: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Strict dictionary matching schemas/lineage-receipt.schema.json."""
        d: Dict[str, Any] = {
            "protocol": self.protocol,
            "receipt_id": self.receipt_id,
            "timestamp": self.timestamp,
            "target_id": self.target_id,
            "verification_status": self.verification_status,
            "root_ancestors": self.root_ancestors,
            "entities": [e.to_dict() for e in self.entities],
            "activities": [a.to_dict() for a in self.activities],
            "edges": [ed.to_dict() for ed in self.edges],
        }
        if self.error_detail:
            d["error_detail"] = self.error_detail
        if self.trace_steps:
            d["trace_steps"] = self.trace_steps
        return d


def validate_lineage(graph: LineageGraph, check_on_disk_hashes: bool = True) -> Tuple[str, Optional[str]]:
    """Strict deterministic topological DAG validation, referential integrity, and content hash check.

    Returns:
        (status, error_detail)
        status in ("intact", "broken_chain", "hash_mismatch", "missing_input", "cycle_detected")
    """
    # 1. Referential integrity: check that all edge references exist in graph
    for edge in graph.edges:
        if edge.type == "used":
            # source is activity, target is entity
            if edge.source_id not in graph.activities:
                return "missing_input", f"Activity {edge.source_id!r} referenced in 'used' edge does not exist"
            if edge.target_id not in graph.entities:
                return "missing_input", f"Entity {edge.target_id!r} consumed by activity {edge.source_id!r} does not exist"
        elif edge.type == "generated":
            # source is activity, target is entity
            if edge.source_id not in graph.activities:
                return "broken_chain", f"Activity {edge.source_id!r} referenced in 'generated' edge does not exist"
            if edge.target_id not in graph.entities:
                return "broken_chain", f"Entity {edge.target_id!r} generated by activity {edge.source_id!r} does not exist"
        elif edge.type == "derived_from":
            # source is derived entity, target is ancestor entity
            if edge.source_id not in graph.entities:
                return "broken_chain", f"Derived entity {edge.source_id!r} does not exist"
            if edge.target_id not in graph.entities:
                return "broken_chain", f"Source entity {edge.target_id!r} in derivation does not exist"
            if edge.source_id == edge.target_id:
                return "cycle_detected", f"Self-derivation loop detected on entity {edge.source_id!r}"

    # 2. Topological DAG cycle check
    # Directed graph: causal flow from upstream entity -> activity -> downstream entity
    adj: Dict[str, List[str]] = {}
    nodes: Set[str] = set()
    for eid in graph.entities:
        nodes.add(eid)
        adj[eid] = []
    for aid in graph.activities:
        nodes.add(aid)
        adj[aid] = []

    for edge in graph.edges:
        if edge.type == "used":
            # entity (input) -> activity
            adj[edge.target_id].append(edge.source_id)
        elif edge.type == "generated":
            # activity -> entity (output)
            adj[edge.source_id].append(edge.target_id)
        elif edge.type == "derived_from":
            # ancestor entity -> derived entity
            adj[edge.target_id].append(edge.source_id)

    # Three-color DFS cycle detection: 0 = unvisited, 1 = visiting (in stack), 2 = visited
    state: Dict[str, int] = {n: 0 for n in nodes}

    def _dfs_cycle(u: str) -> bool:
        state[u] = 1
        for v in adj.get(u, []):
            if state[v] == 1:
                return True
            if state[v] == 0:
                if _dfs_cycle(v):
                    return True
        state[u] = 2
        return False

    for node in nodes:
        if state[node] == 0:
            if _dfs_cycle(node):
                return "cycle_detected", f"Causal cycle detected involving node {node!r}"

    # 3. Optional on-disk content hash verification
    if check_on_disk_hashes:
        for eid, ent in graph.entities.items():
            if ent.sha256 and ent.locator:
                loc_path = Path(ent.locator)
                if loc_path.is_file():
                    computed = compute_file_sha256(loc_path)
                    if computed.lower() != ent.sha256.lower():
                        return (
                            "hash_mismatch",
                            f"Content hash mismatch on entity {eid!r} ({ent.locator}): expected {ent.sha256}, got {computed}",
                        )

    return "intact", None


def trace_origin(
    graph: LineageGraph,
    target_id: str,
    check_on_disk_hashes: bool = True,
) -> LineageReceipt:
    """Deterministically trace the provenance lineage of target_id back to root inputs.

    Performs reverse causal graph traversal, identifies all upstream dependencies,
    collects execution activities, and validates integrity in milliseconds without
    network or LLM dependencies.
    """
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    h_seed = hashlib.sha256(f"{target_id}:{now_str}".encode("utf-8")).hexdigest()[:12]
    receipt_id = f"lin-{h_seed}"

    if target_id not in graph.entities and target_id not in graph.activities:
        return LineageReceipt(
            receipt_id=receipt_id,
            timestamp=now_str,
            target_id=target_id,
            verification_status="missing_input",
            error_detail=f"Target {target_id!r} not found in provenance graph",
        )

    # First validate overall graph sanity
    status, err = validate_lineage(graph, check_on_disk_hashes=check_on_disk_hashes)
    if status != "intact":
        return LineageReceipt(
            receipt_id=receipt_id,
            timestamp=now_str,
            target_id=target_id,
            verification_status=status,
            error_detail=err,
            entities=list(graph.entities.values()),
            activities=list(graph.activities.values()),
            edges=list(graph.edges),
        )

    # Backward traversal from target_id
    # Reverse adjacency: node -> list of upstream sources
    rev_adj: Dict[str, List[Tuple[str, LineageEdge]]] = {}
    for edge in graph.edges:
        if edge.type == "used":
            # causal: entity (target_id) -> activity (source_id)
            # backward: activity -> entity
            rev_adj.setdefault(edge.source_id, []).append((edge.target_id, edge))
        elif edge.type == "generated":
            # causal: activity (source_id) -> entity (target_id)
            # backward: entity -> activity
            rev_adj.setdefault(edge.target_id, []).append((edge.source_id, edge))
        elif edge.type == "derived_from":
            # causal: ancestor (target_id) -> derived (source_id)
            # backward: derived -> ancestor
            rev_adj.setdefault(edge.source_id, []).append((edge.target_id, edge))

    visited_nodes: Set[str] = set()
    included_edges: List[LineageEdge] = []
    queue: List[str] = [target_id]
    visited_nodes.add(target_id)

    while queue:
        curr = queue.pop(0)
        for upstream, edge in rev_adj.get(curr, []):
            included_edges.append(edge)
            if upstream not in visited_nodes:
                visited_nodes.add(upstream)
                queue.append(upstream)

    # Segment visited nodes into entities and activities
    relevant_entities = [graph.entities[nid] for nid in visited_nodes if nid in graph.entities]
    relevant_activities = [graph.activities[nid] for nid in visited_nodes if nid in graph.activities]

    # Find root ancestor entities (entities that have no incoming backward edges in the subgraph)
    # i.e., entities that are never generated by an activity or derived from another entity
    derived_or_generated_targets: Set[str] = set()
    for edge in included_edges:
        if edge.type in ("generated", "derived_from"):
            derived_or_generated_targets.add(edge.source_id if edge.type == "derived_from" else edge.target_id)

    root_ancestors = sorted([
        ent.id for ent in relevant_entities
        if ent.id not in derived_or_generated_targets and ent.id != target_id
    ])
    if not root_ancestors and target_id in graph.entities and not rev_adj.get(target_id):
        # Target itself is a root entity
        root_ancestors = [target_id]

    # Deterministic reconstruction of causal trace steps
    # 按照严格因果拓扑对活动排序 (生产实体的活动必定先于消费该实体的活动)
    act_deps: Dict[str, Set[str]] = {a.id: set() for a in relevant_activities}
    gen_map: Dict[str, str] = {}
    for edge in included_edges:
        if edge.type == "generated":
            gen_map[edge.target_id] = edge.source_id

    for edge in included_edges:
        if edge.type == "used":
            consumer_act = edge.source_id
            used_ent = edge.target_id
            producer_act = gen_map.get(used_ent)
            if producer_act and producer_act != consumer_act and producer_act in act_deps:
                act_deps[consumer_act].add(producer_act)

    sorted_act_ids: List[str] = []
    ready_acts = [aid for aid, deps in act_deps.items() if not deps]
    ready_acts.sort()
    while ready_acts:
        curr = ready_acts.pop(0)
        sorted_act_ids.append(curr)
        for aid, deps in list(act_deps.items()):
            if curr in deps:
                deps.remove(curr)
                if not deps and aid not in sorted_act_ids and aid not in ready_acts:
                    ready_acts.append(aid)
                    ready_acts.sort()

    for a in relevant_activities:
        if a.id not in sorted_act_ids:
            sorted_act_ids.append(a.id)

    act_dict = {a.id: a for a in relevant_activities}
    sorted_activities = [act_dict[aid] for aid in sorted_act_ids]

    trace_steps = []
    step_num = 1
    for act in sorted_activities:
        inputs = [
            e.target_id for e in included_edges
            if e.source_id == act.id and e.type == "used"
        ]
        outputs = [
            e.target_id for e in included_edges
            if e.source_id == act.id and e.type == "generated"
        ]
        trace_steps.append({
            "step_number": step_num,
            "activity_id": act.id,
            "inputs": sorted(inputs),
            "outputs": sorted(outputs),
        })
        step_num += 1

    return LineageReceipt(
        receipt_id=receipt_id,
        timestamp=now_str,
        target_id=target_id,
        verification_status="intact",
        root_ancestors=root_ancestors,
        entities=relevant_entities,
        activities=relevant_activities,
        edges=included_edges,
        trace_steps=trace_steps,
    )
