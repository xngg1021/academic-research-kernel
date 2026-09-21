# -*- coding: utf-8 -*-
"""Research Object Provenance Kernel & Lineage Receipt v1.

Deterministic, content-addressed scientific derivation and provenance kernel
grounded in W3C PROV-DM core concepts (Entity, Activity, used, generated, derived_from).

Core Invariants:
1. Strict type enforcement and fail-fast validation for all entities, activities, and edges.
2. Disjoint entity and activity ID namespaces with strict idempotent registration (including timestamp).
3. Structural tuple edge identity with exact-idempotent registration (delimiter-collision-free).
4. Causal DAG acyclicity with iterative Kahn / topological cycle detection.
5. Content-addressed file verification: missing on-disk files trigger 'missing_artifact',
   tampered contents trigger 'hash_mismatch', partial local coverage triggers 'partial',
   and unverified/disabled verification triggers 'unchecked'. Never collapses UNKNOWN into 'intact'.
6. Full edge canonical sorting by (type, source, target, activity, canonical_metadata_json).
7. Strict derivation-activity binding: claimed derivation activity must causally touch source or derived entity.
8. Comprehensive URI scheme recognition (http, https, s3, gs, hdfs, etc.) preventing false missing_artifact.
9. Separation of Lineage Content Identity (lineage_digest) from Verification Receipt Identity (receipt_digest / receipt_id).
10. Immutable, deep-copied LineageReceipt snapshots.
11. Millisecond-level target-scoped backward traversal back to root raw inputs.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Dict, Iterator, List, Mapping, Optional, Set, Tuple

try:
    if __package__ and __package__.startswith("academic_research_kernel"):
        from academic_research_kernel.shared_contracts.evidence import LineageVerificationContext, _replay_lineage_content_verification
    else:
        from shared_contracts.evidence import LineageVerificationContext, _replay_lineage_content_verification
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    if __package__ and __package__.startswith("academic_research_kernel"):
        from academic_research_kernel.shared_contracts.evidence import LineageVerificationContext, _replay_lineage_content_verification
    else:
        from shared_contracts.evidence import LineageVerificationContext, _replay_lineage_content_verification

__all__ = [
    "Entity",
    "Activity",
    "LineageEdge",
    "LineageGraph",
    "LineageReceipt",
    "validate_lineage",
    "trace_origin",
    "compute_file_sha256",
    "canonical_edge_tuple",
    "edge_dict_sort_key",
    "VALID_ENTITY_TYPES",
    "VALID_ACTIVITY_TYPES",
    "VALID_EDGE_TYPES",
]

VALID_ENTITY_TYPES: Set[str] = {
    "data_snapshot",
    "code_file",
    "environment_spec",
    "statistic_artifact",
    "table_cell",
    "figure_artifact",
    "generic_entity",
}

VALID_ACTIVITY_TYPES: Set[str] = {
    "data_cleaning",
    "computation_run",
    "statistical_analysis",
    "table_extraction",
    "render_run",
    "generic_activity",
}

VALID_EDGE_TYPES: Set[str] = {
    "used",
    "generated",
    "derived_from",
}

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")
REMOTE_URI_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


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
    type: str
    sha256: Optional[str] = None
    locator: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {self.type!r}. Must be one of {sorted(VALID_ENTITY_TYPES)}")
        if self.sha256 is not None:
            self.sha256 = self.sha256.strip().lower()
            if not SHA256_REGEX.match(self.sha256):
                raise ValueError(f"Invalid SHA256 format for entity {self.id!r}: {self.sha256!r}. Must be 64 lowercase hex digits.")
        self.metadata = copy.deepcopy(self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"id": self.id, "type": self.type}
        if self.sha256:
            d["sha256"] = self.sha256
        if self.locator is not None:
            d["locator"] = str(self.locator)
        if self.metadata:
            d["metadata"] = copy.deepcopy(self.metadata)
        return d


@dataclass
class Activity:
    id: str
    type: str
    command: Optional[str] = None
    script_id: Optional[str] = None
    commit_sha: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.type not in VALID_ACTIVITY_TYPES:
            raise ValueError(f"Invalid activity type: {self.type!r}. Must be one of {sorted(VALID_ACTIVITY_TYPES)}")
        self.parameters = copy.deepcopy(self.parameters)
        self.environment = copy.deepcopy(self.environment)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"id": self.id, "type": self.type}
        if self.command:
            d["command"] = self.command
        if self.script_id:
            d["script_id"] = self.script_id
        if self.commit_sha:
            d["commit_sha"] = self.commit_sha
        if self.parameters:
            d["parameters"] = copy.deepcopy(self.parameters)
        if self.environment:
            d["environment"] = copy.deepcopy(self.environment)
        if self.timestamp:
            d["timestamp"] = self.timestamp
        return d


@dataclass
class LineageEdge:
    type: str
    source_id: str
    target_id: str
    activity_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.type not in VALID_EDGE_TYPES:
            raise ValueError(f"Invalid edge type: {self.type!r}. Must be one of {sorted(VALID_EDGE_TYPES)}")
        self.metadata = copy.deepcopy(self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": self.type,
            "source_id": self.source_id,
            "target_id": self.target_id,
        }
        if self.activity_id:
            d["activity_id"] = self.activity_id
        if self.metadata:
            d["metadata"] = copy.deepcopy(self.metadata)
        return d


def canonical_edge_tuple(edge: LineageEdge) -> Tuple[str, str, str, str, str]:
    """Compute canonical 5-tuple for edge identity including activity_id and sorted metadata."""
    meta_json = json.dumps(
        edge.metadata,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (
        edge.type,
        edge.source_id,
        edge.target_id,
        edge.activity_id or "",
        meta_json,
    )


def edge_dict_sort_key(d: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    """Sort key for canonical serialized edges matching canonical_edge_tuple."""
    meta_json = json.dumps(
        d.get("metadata", {}),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (
        d.get("type", ""),
        d.get("source_id", ""),
        d.get("target_id", ""),
        d.get("activity_id") or "",
        meta_json,
    )


def _freeze_receipt_json(value: Any) -> Any:
    if isinstance(value, _FrozenReceiptMap):
        return value
    if isinstance(value, collections.abc.Mapping):
        return _FrozenReceiptMap(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_receipt_json(item) for item in value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Lineage receipt values must be finite JSON numbers")
        return value
    raise TypeError(
        f"Lineage receipt value {type(value).__name__!r} is outside the JSON domain"
    )


def _thaw_receipt_json(value: Any) -> Any:
    if isinstance(value, _FrozenReceiptMap):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_thaw_receipt_json(item) for item in value]
    return value


class _FrozenReceiptMap(collections.abc.Mapping):
    """Recursively immutable JSON mapping used inside LineageReceipt."""

    __slots__ = ("_data",)

    def __init__(self, value: Mapping[str, Any]):
        frozen: Dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Lineage receipt object keys must be strings")
            frozen[key] = _freeze_receipt_json(item)
        object.__setattr__(self, "_data", MappingProxyType(frozen))

    def __setattr__(self, key: str, value: Any) -> None:
        raise TypeError("Lineage receipt mappings do not support mutation")

    def __delattr__(self, key: str) -> None:
        raise TypeError("Lineage receipt mappings do not support mutation")

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __deepcopy__(self, memo: Dict[int, Any]) -> "_FrozenReceiptMap":
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {key: _thaw_receipt_json(value) for key, value in self._data.items()}


class LineageGraph:
    """In-memory causal derivation graph container enforcing disjoint namespaces and referential integrity."""

    def __init__(self, root_dir: Optional[str | Path] = None):
        self.entities: Dict[str, Entity] = {}
        self.activities: Dict[str, Activity] = {}
        self.edges: List[LineageEdge] = []
        self._edge_keys: Set[Tuple[str, str, str, str, str]] = set()
        self._all_ids: Dict[str, str] = {}  # id -> "entity" | "activity"
        self._generating_activities: Dict[str, str] = {}  # entity_id -> activity_id (single generator rule)
        self.root_dir: Optional[Path] = Path(root_dir).resolve() if root_dir else None

    def add_entity(
        self,
        id: str,
        type: str,
        sha256: Optional[str] = None,
        locator: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Entity:
        id_str = str(id).strip()
        if id_str in self._all_ids and self._all_ids[id_str] != "entity":
            raise ValueError(f"Namespace collision: ID {id_str!r} is already registered as an activity.")

        loc_str = str(locator) if locator is not None else None
        new_ent = Entity(id=id_str, type=type, sha256=sha256, locator=loc_str, metadata=metadata or {})

        # Idempotent registration check (P1-02)
        if id_str in self.entities:
            existing = self.entities[id_str]
            if (
                existing.type != new_ent.type
                or existing.sha256 != new_ent.sha256
                or existing.locator != new_ent.locator
                or existing.metadata != new_ent.metadata
            ):
                raise ValueError(
                    f"Conflicting entity registration for ID {id_str!r}: "
                    f"existing={existing.to_dict()}, new={new_ent.to_dict()}"
                )
            return existing

        self.entities[id_str] = new_ent
        self._all_ids[id_str] = "entity"
        return new_ent

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
        id_str = str(id).strip()
        if id_str in self._all_ids and self._all_ids[id_str] != "activity":
            raise ValueError(f"Namespace collision: ID {id_str!r} is already registered as an entity.")

        new_act = Activity(
            id=id_str,
            type=type,
            command=command,
            script_id=script_id,
            commit_sha=commit_sha,
            parameters=parameters or {},
            environment=environment or {},
            timestamp=timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        # Idempotent registration check (P1-02 & timestamp comparison)
        if id_str in self.activities:
            existing = self.activities[id_str]
            if (
                existing.type != new_act.type
                or existing.command != new_act.command
                or existing.script_id != new_act.script_id
                or existing.commit_sha != new_act.commit_sha
                or existing.parameters != new_act.parameters
                or existing.environment != new_act.environment
                or (timestamp is not None and existing.timestamp != new_act.timestamp)
            ):
                raise ValueError(
                    f"Conflicting activity registration for ID {id_str!r}: "
                    f"existing={existing.to_dict()}, new={new_act.to_dict()}"
                )
            return existing

        self.activities[id_str] = new_act
        self._all_ids[id_str] = "activity"
        return new_act

    def record_used(self, activity_id: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Record that an Activity consumed an Entity as input (idempotent)."""
        act_id = str(activity_id).strip()
        ent_id = str(entity_id).strip()
        edge = LineageEdge(type="used", source_id=act_id, target_id=ent_id, metadata=metadata or {})
        k = canonical_edge_tuple(edge)
        if k not in self._edge_keys:
            self._edge_keys.add(k)
            self.edges.append(edge)

    def record_generated(self, activity_id: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Record that an Activity generated an Entity as output (single-producer invariant, idempotent)."""
        act_id = str(activity_id).strip()
        ent_id = str(entity_id).strip()
        if ent_id in self._generating_activities and self._generating_activities[ent_id] != act_id:
            raise ValueError(
                f"Single-producer violation: Entity {ent_id!r} is already generated by activity "
                f"{self._generating_activities[ent_id]!r}; cannot be re-generated by {act_id!r}."
            )
        self._generating_activities[ent_id] = act_id
        edge = LineageEdge(type="generated", source_id=act_id, target_id=ent_id, metadata=metadata or {})
        k = canonical_edge_tuple(edge)
        if k not in self._edge_keys:
            self._edge_keys.add(k)
            self.edges.append(edge)

    def record_derivation(
        self,
        derived_entity_id: str,
        source_entity_id: str,
        activity_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Record that derived_entity_id was derived from source_entity_id (idempotent)."""
        d_id = str(derived_entity_id).strip()
        s_id = str(source_entity_id).strip()
        act_id = str(activity_id).strip() if activity_id else None
        edge = LineageEdge(type="derived_from", source_id=d_id, target_id=s_id, activity_id=act_id, metadata=metadata or {})
        k = canonical_edge_tuple(edge)
        if k not in self._edge_keys:
            self._edge_keys.add(k)
            self.edges.append(edge)


@dataclass(frozen=True)
class LineageReceipt:
    protocol: str = "lineage-receipt-1.0"
    receipt_id: str = ""
    lineage_digest: str = ""
    receipt_digest: str = ""
    timestamp: str = ""
    target_id: str = ""
    verification_status: str = "unchecked"
    topology_status: str = "valid_dag"
    content_verification: str = "unchecked"
    error_detail: Optional[str] = None
    root_ancestors: Tuple[str, ...] = field(default_factory=tuple)
    entities: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    activities: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    edges: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    trace_steps: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    _content_root: Optional[str] = field(default=None, repr=False, compare=False)
    _verification_context: Optional[LineageVerificationContext] = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_ancestors", tuple(self.root_ancestors))
        for field_name in ("entities", "activities", "edges", "trace_steps"):
            values = getattr(self, field_name)
            object.__setattr__(
                self,
                field_name,
                tuple(_FrozenReceiptMap(value) for value in values),
            )

    @property
    def content_digest(self) -> str:
        """Alias for lineage_digest maintaining backward compatibility."""
        return self.lineage_digest

    def to_dict(self) -> Dict[str, Any]:
        """Deepcopy and serialize strictly matching schemas/lineage-receipt.schema.json."""
        d: Dict[str, Any] = {
            "protocol": self.protocol,
            "receipt_id": self.receipt_id,
            "lineage_digest": self.lineage_digest,
            "receipt_digest": self.receipt_digest,
            "content_digest": self.content_digest,
            "timestamp": self.timestamp,
            "target_id": self.target_id,
            "verification_status": self.verification_status,
            "topology_status": self.topology_status,
            "content_verification": self.content_verification,
            "root_ancestors": list(self.root_ancestors),
            "entities": [_thaw_receipt_json(e) for e in self.entities],
            "activities": [_thaw_receipt_json(a) for a in self.activities],
            "edges": [_thaw_receipt_json(ed) for ed in self.edges],
        }
        if self.error_detail is not None:
            d["error_detail"] = self.error_detail
        if self.trace_steps:
            d["trace_steps"] = [_thaw_receipt_json(s) for s in self.trace_steps]
        return copy.deepcopy(d)


def _resolve_locator_path(locator: str, root_dir: Optional[Path] = None) -> Tuple[Optional[Path], bool]:
    """Parse local filesystem path from locator string, discarding URI schemes or anchors.

    Note on trust boundaries:
        root_dir provides an explicit base anchor for relative paths, completely
        eliminating implicit process CWD fallback across executions. It acts as
        a deterministic locator base, not a hardened containment sandbox (e.g.
        explicit parent-directory traversals like '../' are resolved from root_dir).

    Returns:
        (resolved_path, is_unanchored_relative)
        If locator is a relative local path and root_dir is None, returns (None, True).
        If locator is remote/URI or empty, returns (None, False).
        If resolvable, returns (absolute_path, False).
    """
    if not locator:
        return None, False
    loc_str = str(locator).strip()
    if REMOTE_URI_REGEX.match(loc_str) or loc_str.startswith(("urn:", "doi:")):
        return None, False
    clean_path = loc_str.split("#", 1)[0].split("?", 1)[0]
    p = Path(clean_path)
    if not p.is_absolute():
        if root_dir is not None:
            return (root_dir / p).resolve(), False
        # Disallow implicit process CWD fallback to guarantee determinism across environments
        return None, True
    return p.resolve(), False


def _graph_verification_context(graph: LineageGraph) -> LineageVerificationContext:
    """Preserve trusted Python absolute-file API without ambient wire authority."""
    paths = []
    if graph.root_dir is None:
        for entity in graph.entities.values():
            if entity.locator:
                path, _ = _resolve_locator_path(entity.locator)
                if path is not None:
                    paths.append(path)
    return LineageVerificationContext(content_root=graph.root_dir, authorized_paths=tuple(paths))


def validate_lineage(
    graph: LineageGraph,
    check_on_disk_hashes: bool = True,
    target_scope: Optional[Set[str]] = None,
    *, verification_context: Optional[LineageVerificationContext] = None,
) -> Tuple[str, str, str, Optional[str]]:
    """Strict deterministic topological DAG validation, referential integrity, and content hash checks.

    Returns:
        (verification_status, topology_status, content_verification, error_detail)
        verification_status: "intact" | "partial" | "unchecked" | "broken_chain" | "hash_mismatch" | "missing_artifact" | "missing_input" | "cycle_detected"
    """
    scoped_entities = graph.entities
    scoped_activities = graph.activities
    scoped_edges = sorted(graph.edges, key=canonical_edge_tuple)

    if target_scope is not None:
        scoped_entities = {k: v for k, v in graph.entities.items() if k in target_scope}
        scoped_activities = {k: v for k, v in graph.activities.items() if k in target_scope}
        scoped_edges = sorted((
            e for e in graph.edges
            if e.source_id in target_scope and e.target_id in target_scope
        ), key=canonical_edge_tuple)

    activity_inputs: Dict[str, Set[str]] = collections.defaultdict(set)
    activity_outputs: Dict[str, Set[str]] = collections.defaultdict(set)
    for edge in scoped_edges:
        if edge.type == "used":
            activity_inputs[edge.source_id].add(edge.target_id)
        elif edge.type == "generated":
            activity_outputs[edge.source_id].add(edge.target_id)

    # 1. Referential integrity on edges
    for edge in scoped_edges:
        if edge.type == "used":
            if edge.source_id not in graph.activities:
                return "missing_input", "missing_input", "unchecked", f"Activity {edge.source_id!r} referenced in 'used' edge does not exist"
            if edge.target_id not in graph.entities:
                return "missing_input", "missing_input", "unchecked", f"Entity {edge.target_id!r} consumed by activity {edge.source_id!r} does not exist"
        elif edge.type == "generated":
            if edge.source_id not in graph.activities:
                return "broken_chain", "broken_chain", "unchecked", f"Activity {edge.source_id!r} referenced in 'generated' edge does not exist"
            if edge.target_id not in graph.entities:
                return "broken_chain", "broken_chain", "unchecked", f"Entity {edge.target_id!r} generated by activity {edge.source_id!r} does not exist"
        elif edge.type == "derived_from":
            if edge.source_id not in graph.entities:
                return "broken_chain", "broken_chain", "unchecked", f"Derived entity {edge.source_id!r} does not exist"
            if edge.target_id not in graph.entities:
                return "broken_chain", "broken_chain", "unchecked", f"Source entity {edge.target_id!r} in derivation does not exist"
            if edge.source_id == edge.target_id:
                return "cycle_detected", "cycle_detected", "unchecked", f"Self-derivation loop detected on entity {edge.source_id!r}"
            # Strict validation of derivation activity and causal binding (P2)
            if edge.activity_id:
                if edge.activity_id not in graph.activities:
                    return "broken_chain", "broken_chain", "unchecked", f"Derivation activity {edge.activity_id!r} does not exist in activities"
                act_inputs = activity_inputs.get(edge.activity_id, set())
                act_outputs = activity_outputs.get(edge.activity_id, set())
                if edge.target_id not in act_inputs and edge.source_id not in act_outputs:
                    return (
                        "broken_chain",
                        "broken_chain",
                        "unchecked",
                        f"Derivation activity {edge.activity_id!r} is detached: it neither consumed source {edge.target_id!r} nor generated derived {edge.source_id!r}",
                    )

    # 1b. Activity script_id referential integrity
    for aid in sorted(scoped_activities):
        act = scoped_activities[aid]
        if act.script_id:
            if act.script_id not in graph.entities:
                return "missing_input", "missing_input", "unchecked", f"Activity {aid!r} references missing script entity {act.script_id!r}"
            if graph.entities[act.script_id].type != "code_file":
                return "broken_chain", "broken_chain", "unchecked", f"Activity {aid!r} script {act.script_id!r} is not a 'code_file' entity"

    # 2. Iterative DAG cycle check via Kahn's algorithm
    nodes: Set[str] = set(scoped_entities.keys()) | set(scoped_activities.keys())
    adj: Dict[str, List[str]] = {n: [] for n in nodes}
    indegree: Dict[str, int] = {n: 0 for n in nodes}

    for edge in scoped_edges:
        u, v = None, None
        if edge.type == "used":
            u, v = edge.target_id, edge.source_id
        elif edge.type == "generated":
            u, v = edge.source_id, edge.target_id
        elif edge.type == "derived_from":
            u, v = edge.target_id, edge.source_id

        if u in adj and v in adj:
            adj[u].append(v)
            indegree[v] += 1

    queue = collections.deque([n for n, d in indegree.items() if d == 0])
    visited_count = 0
    while queue:
        curr = queue.popleft()
        visited_count += 1
        for neighbor in adj[curr]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count < len(nodes):
        return "cycle_detected", "cycle_detected", "unchecked", "Causal dependency cycle detected in graph"

    # Producer and verifier share authority, containment and cumulative budget.
    context = verification_context or _graph_verification_context(graph)
    overall, content, detail = _replay_lineage_content_verification(
        [scoped_entities[eid].to_dict() for eid in sorted(scoped_entities)],
        check_on_disk_hashes=check_on_disk_hashes,
        **context.content_options(),
    )
    return overall, "valid_dag", content, detail


def _canonical_lineage_digest(
    target_id: str,
    root_ancestors: List[str],
    entities: List[Dict[str, Any]],
    activities: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    trace_steps: List[Dict[str, Any]],
) -> str:
    """Compute deterministic content digest across sorted canonical derivation graph payload."""
    payload = {
        "protocol": "lineage-receipt-1.0",
        "target_id": target_id,
        "root_ancestors": sorted(root_ancestors),
        "entities": sorted(entities, key=lambda x: x["id"]),
        "activities": sorted(activities, key=lambda x: x["id"]),
        "edges": sorted(edges, key=edge_dict_sort_key),
        "trace_steps": trace_steps,
    }
    canon_bytes = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canon_bytes).hexdigest().lower()


def _canonical_receipt_digest(
    lineage_digest: str,
    target_id: str,
    verification_status: str,
    topology_status: str,
    content_verification: str,
    error_detail: Optional[str],
    check_on_disk_hashes: bool,
) -> str:
    """Compute deterministic receipt digest combining lineage graph digest with verification assessment."""
    payload = {
        "lineage_digest": lineage_digest,
        "target_id": target_id,
        "verification_status": verification_status,
        "topology_status": topology_status,
        "content_verification": content_verification,
        "error_detail": error_detail or "",
        "check_on_disk_hashes": check_on_disk_hashes,
    }
    canon_bytes = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canon_bytes).hexdigest().lower()


def trace_origin(
    graph: LineageGraph,
    target_id: str,
    check_on_disk_hashes: bool = True,
    *, verification_context: Optional[LineageVerificationContext] = None,
) -> LineageReceipt:
    """Deterministically trace the provenance lineage of target_id back to root inputs."""
    verification_context = verification_context or _graph_verification_context(graph)
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    tid = str(target_id).strip()

    if tid not in graph.entities and tid not in graph.activities:
        fail_rec_digest = _canonical_receipt_digest(
            lineage_digest="0" * 64,
            target_id=tid,
            verification_status="missing_input",
            topology_status="missing_input",
            content_verification="unchecked",
            error_detail=f"Target {tid!r} not found in provenance graph",
            check_on_disk_hashes=check_on_disk_hashes,
        )
        return LineageReceipt(
            receipt_id=f"rec-{fail_rec_digest[:32]}",
            lineage_digest="0" * 64,
            receipt_digest=fail_rec_digest,
            timestamp=now_str,
            target_id=tid,
            verification_status="missing_input",
            topology_status="missing_input",
            content_verification="unchecked",
            error_detail=f"Target {tid!r} not found in provenance graph",
            _content_root=str(graph.root_dir) if graph.root_dir is not None else None,
            _verification_context=verification_context,
        )

    # 1. Reverse graph traversal to isolate target's causal dependency closure
    rev_adj: Dict[str, List[Tuple[str, LineageEdge]]] = {}
    for edge in graph.edges:
        if edge.type == "used":
            rev_adj.setdefault(edge.source_id, []).append((edge.target_id, edge))
        elif edge.type == "generated":
            rev_adj.setdefault(edge.target_id, []).append((edge.source_id, edge))
        elif edge.type == "derived_from":
            rev_adj.setdefault(edge.source_id, []).append((edge.target_id, edge))
            if edge.activity_id:
                rev_adj.setdefault(edge.source_id, []).append((edge.activity_id, edge))

    visited_nodes: Set[str] = set([tid])
    included_edges: List[LineageEdge] = []
    seen_edge_keys: Set[Tuple[str, str, str, str, str]] = set()
    queue = collections.deque([tid])

    while queue:
        curr = queue.popleft()
        for upstream, edge in rev_adj.get(curr, []):
            ek = canonical_edge_tuple(edge)
            if ek not in seen_edge_keys:
                seen_edge_keys.add(ek)
                included_edges.append(edge)
            if upstream not in visited_nodes:
                visited_nodes.add(upstream)
                queue.append(upstream)

    # Include script entities for visited activities
    for nid in list(visited_nodes):
        if nid in graph.activities:
            s_id = graph.activities[nid].script_id
            if s_id and s_id in graph.entities:
                visited_nodes.add(s_id)

    # 2. Target-scoped validation
    v_stat, topo_stat, cont_stat, err_msg = validate_lineage(
        graph,
        check_on_disk_hashes=check_on_disk_hashes,
        target_scope=visited_nodes,
        verification_context=verification_context,
    )

    relevant_entities = sorted(
        [graph.entities[nid].to_dict() for nid in visited_nodes if nid in graph.entities],
        key=lambda x: x["id"],
    )
    relevant_activities = sorted(
        [graph.activities[nid].to_dict() for nid in visited_nodes if nid in graph.activities],
        key=lambda x: x["id"],
    )
    canonical_edges = sorted(
        [e.to_dict() for e in included_edges],
        key=edge_dict_sort_key,
    )

    # Calculate partial lineage digest even on failure
    lineage_digest = _canonical_lineage_digest(
        target_id=tid,
        root_ancestors=[],
        entities=relevant_entities,
        activities=relevant_activities,
        edges=canonical_edges,
        trace_steps=[],
    )
    receipt_digest = _canonical_receipt_digest(
        lineage_digest=lineage_digest,
        target_id=tid,
        verification_status=v_stat,
        topology_status=topo_stat,
        content_verification=cont_stat,
        error_detail=err_msg,
        check_on_disk_hashes=check_on_disk_hashes,
    )
    receipt_id = f"rec-{receipt_digest[:32]}"

    if topo_stat != "valid_dag" or cont_stat in ("hash_mismatch", "missing_artifact"):
        return LineageReceipt(
            receipt_id=receipt_id,
            lineage_digest=lineage_digest,
            receipt_digest=receipt_digest,
            timestamp=now_str,
            target_id=tid,
            verification_status=v_stat,
            topology_status=topo_stat,
            content_verification=cont_stat,
            error_detail=err_msg,
            entities=tuple(relevant_entities),
            activities=tuple(relevant_activities),
            edges=tuple(canonical_edges),
            _content_root=str(graph.root_dir) if graph.root_dir is not None else None,
            _verification_context=verification_context,
        )

    # 3. Identify root ancestor entities in causal subgraph
    derived_or_generated: Set[str] = set()
    for edge in included_edges:
        if edge.type == "generated":
            derived_or_generated.add(edge.target_id)
        elif edge.type == "derived_from":
            derived_or_generated.add(edge.source_id)

    root_ancestors = sorted([
        ent["id"] for ent in relevant_entities
        if ent["id"] not in derived_or_generated and ent["id"] != tid
    ])
    if not root_ancestors and tid in graph.entities and not rev_adj.get(tid):
        root_ancestors = [tid]

    # 4. Topological causal ordering of activities
    act_ids_in_closure = {a["id"] for a in relevant_activities}
    act_deps: Dict[str, Set[str]] = {aid: set() for aid in act_ids_in_closure}
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

    for aid in sorted(act_ids_in_closure):
        if aid not in sorted_act_ids:
            sorted_act_ids.append(aid)

    # Pre-index inputs and outputs by activity
    inputs_by_act: Dict[str, List[str]] = collections.defaultdict(list)
    outputs_by_act: Dict[str, List[str]] = collections.defaultdict(list)
    for edge in included_edges:
        if edge.type == "used":
            inputs_by_act[edge.source_id].append(edge.target_id)
        elif edge.type == "generated":
            outputs_by_act[edge.source_id].append(edge.target_id)

    trace_steps = []
    step_num = 1
    for aid in sorted_act_ids:
        trace_steps.append({
            "step_number": step_num,
            "activity_id": aid,
            "inputs": sorted(inputs_by_act[aid]),
            "outputs": sorted(outputs_by_act[aid]),
        })
        step_num += 1

    # 5. Separation of lineage_digest and receipt_digest
    full_lineage_digest = _canonical_lineage_digest(
        target_id=tid,
        root_ancestors=root_ancestors,
        entities=relevant_entities,
        activities=relevant_activities,
        edges=canonical_edges,
        trace_steps=trace_steps,
    )
    final_receipt_digest = _canonical_receipt_digest(
        lineage_digest=full_lineage_digest,
        target_id=tid,
        verification_status=v_stat,
        topology_status=topo_stat,
        content_verification=cont_stat,
        error_detail=err_msg,
        check_on_disk_hashes=check_on_disk_hashes,
    )
    final_receipt_id = f"rec-{final_receipt_digest[:32]}"

    return LineageReceipt(
        protocol="lineage-receipt-1.0",
        receipt_id=final_receipt_id,
        lineage_digest=full_lineage_digest,
        receipt_digest=final_receipt_digest,
        timestamp=now_str,
        target_id=tid,
        verification_status=v_stat,
        topology_status=topo_stat,
        content_verification=cont_stat,
        error_detail=err_msg,
        root_ancestors=tuple(root_ancestors),
        entities=tuple(relevant_entities),
        activities=tuple(relevant_activities),
        edges=tuple(canonical_edges),
        trace_steps=tuple(trace_steps),
        _content_root=str(graph.root_dir) if graph.root_dir is not None else None,
        _verification_context=verification_context,
    )
