"""Delta sync logic — push resolution, pull assembly, bootstrap, conflict handling.

Conflict resolution rules (from architecture Section 10.5):
  - Venue metadata:       latest timestamp wins, log the merge
  - Venue zones:          union — keep both
  - Zone connections:     deduplicate by from/to zone pair
  - Perch points:         merge statistics (sum attempts, sum successes)
  - Surface assessments:  append-only, no conflict
  - Operations:           unique per workstation, no conflict
  - Alerts:               unique per operation, no conflict
  - WM nodes (specific):  unique per workstation+operation
  - WM nodes (pattern):   cloud is authoritative for patterns/principles
  - Drone profiles:       latest timestamp wins
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.workstation import Workstation
from app.models.venue import Venue
from app.models.venue_zone import VenueZone
from app.models.zone_connection import ZoneConnection
from app.models.perch_point import PerchPoint
from app.models.surface_assessment import SurfaceAssessment
from app.models.operation import Operation
from app.models.principal import Principal
from app.models.alert import Alert
from app.models.drone import Drone
from app.models.wm_node import WMNode
from app.models.wm_edge import WMEdge
from app.models.sync_event import SyncEvent
from app.models.kit import Kit

logger = logging.getLogger(__name__)

TABLE_MODEL_MAP = {
    "venues": Venue,
    "venue_zones": VenueZone,
    "zone_connections": ZoneConnection,
    "perch_points": PerchPoint,
    "surface_assessments": SurfaceAssessment,
    "operations": Operation,
    "principals": Principal,
    "alerts": Alert,
    "drones": Drone,
    "wm_nodes": WMNode,
    "wm_edges": WMEdge,
}

SYNCABLE_MODELS = [
    Venue, VenueZone, ZoneConnection, PerchPoint, Principal,
    Drone, WMNode, WMEdge,
]


class SyncService:
    def apply_push(
        self,
        db: Session,
        customer: Customer,
        workstation: Workstation,
        entities: list,
    ) -> Dict[str, Any]:
        accepted = 0
        rejected = 0
        conflicts: List[Dict[str, Any]] = []

        for entity in entities:
            model_cls = TABLE_MODEL_MAP.get(entity.table)
            if not model_cls:
                rejected += 1
                conflicts.append({"id": entity.id, "reason": f"Unknown table: {entity.table}"})
                continue

            existing = db.query(model_cls).filter(model_cls.id == entity.id).first()

            if existing:
                resolution = self._resolve_conflict(entity.table, existing, entity.data)
                if resolution == "reject":
                    rejected += 1
                    conflicts.append({"id": entity.id, "table": entity.table, "reason": "cloud_authoritative"})
                    continue
                elif resolution == "merge_perch":
                    existing.attempt_count = (existing.attempt_count or 0) + entity.data.get("attempt_count", 0)
                    existing.success_count = (existing.success_count or 0) + entity.data.get("success_count", 0)
                    existing.cloud_version = (existing.cloud_version or 0) + 1
                else:
                    for key, value in entity.data.items():
                        if key not in ("id", "customer_id"):
                            setattr(existing, key, value)
                    existing.cloud_version = (existing.cloud_version or 0) + 1
                    existing.source_workstation_id = workstation.id
            else:
                data = {**entity.data}
                data["id"] = entity.id
                data["customer_id"] = customer.id
                data["source_workstation_id"] = workstation.id
                data["cloud_version"] = 1
                obj = model_cls(**data)
                db.add(obj)

            accepted += 1

        max_version = self._current_max_version(db, customer)
        new_version = max_version + 1

        sync_evt = SyncEvent(
            customer_id=customer.id,
            workstation_id=workstation.id,
            direction="push",
            entity_counts={"accepted": accepted, "rejected": rejected},
            status="completed",
            cloud_version_before=max_version,
            cloud_version_after=new_version,
        )
        db.add(sync_evt)
        db.commit()

        return {
            "accepted": accepted,
            "rejected": rejected,
            "new_cloud_version": new_version,
            "conflicts": conflicts,
        }

    def build_pull(self, db: Session, customer: Customer, since: int) -> Dict[str, Any]:
        entities = []
        for model_cls in SYNCABLE_MODELS:
            if not hasattr(model_cls, "cloud_version"):
                continue
            rows = (
                db.query(model_cls)
                .filter(
                    model_cls.customer_id == customer.id,
                    model_cls.cloud_version > since,
                )
                .all()
            )
            table_name = model_cls.__tablename__
            for row in rows:
                entities.append({
                    "table": table_name,
                    "id": str(row.id),
                    "data": self._row_to_dict(row),
                    "cloud_version": row.cloud_version,
                })

        current_version = self._current_max_version(db, customer)
        return {"entities": entities, "cloud_version": current_version}

    def build_bootstrap(self, db: Session, customer: Customer) -> Dict[str, Any]:
        def _dump(model_cls):
            rows = db.query(model_cls).filter(model_cls.customer_id == customer.id).all()
            return [self._row_to_dict(row) for row in rows]

        return {
            "venues": _dump(Venue),
            "venue_zones": _dump(VenueZone),
            "zone_connections": _dump(ZoneConnection),
            "perch_points": _dump(PerchPoint),
            "kits": _dump(Kit),
            "drones": _dump(Drone),
            "principals": _dump(Principal),
            "wm_nodes": _dump(WMNode),
            "wm_edges": _dump(WMEdge),
            "cloud_version": self._current_max_version(db, customer),
        }

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _resolve_conflict(self, table: str, existing: Any, incoming: Dict) -> str:
        if table in ("surface_assessments", "operations", "alerts"):
            return "accept"

        if table == "wm_nodes":
            if existing.abstraction_level in ("pattern", "principle"):
                return "reject"
            return "accept"

        if table == "perch_points":
            return "merge_perch"

        if table == "drones":
            incoming_ts = incoming.get("updated_at")
            if incoming_ts and existing.updated_at:
                if str(incoming_ts) > str(existing.updated_at):
                    return "accept"
                return "reject"
            return "accept"

        if table == "venues":
            incoming_ts = incoming.get("updated_at")
            if incoming_ts and existing.updated_at:
                if str(incoming_ts) > str(existing.updated_at):
                    return "accept"
                return "reject"
            return "accept"

        return "accept"

    def _current_max_version(self, db: Session, customer: Customer) -> int:
        """Return the highest cloud_version across all syncable tables."""
        max_v = 0
        for model_cls in SYNCABLE_MODELS:
            if not hasattr(model_cls, "cloud_version"):
                continue
            result = (
                db.query(sa_func.max(model_cls.cloud_version))
                .filter(model_cls.customer_id == customer.id)
                .scalar()
            )
            if result and result > max_v:
                max_v = result
        return max_v

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        d = {}
        for col in row.__table__.columns:
            val = getattr(row, col.name)
            if isinstance(val, datetime):
                val = val.isoformat()
            elif hasattr(val, "hex"):  # UUID
                val = str(val)
            d[col.name] = val
        return d


sync_service = SyncService()
