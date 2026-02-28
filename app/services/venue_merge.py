"""Venue merge logic for when multiple workstations contribute to the same venue."""

import logging
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.venue import Venue

logger = logging.getLogger(__name__)


class VenueMergeService:
    def merge_venue_update(
        self,
        db: Session,
        existing: Venue,
        incoming: Dict[str, Any],
    ) -> Venue:
        """Merge an incoming venue update with an existing venue record.

        Strategy: latest timestamp wins for scalar fields. Deployment stats
        are summed. Tags are unioned.
        """
        incoming_ts = incoming.get("updated_at", "")
        existing_ts = str(existing.updated_at) if existing.updated_at else ""

        if incoming_ts > existing_ts:
            scalar_fields = [
                "name", "type", "environment", "address", "lat", "lon",
                "floor_plan_source", "floor_plan_blob_key",
                "venue_model_blob_key", "notes",
            ]
            for field in scalar_fields:
                if field in incoming and incoming[field] is not None:
                    setattr(existing, field, incoming[field])

        if "deployment_count" in incoming:
            existing.deployment_count = max(
                existing.deployment_count or 0,
                incoming.get("deployment_count", 0),
            )

        if "tags" in incoming and incoming["tags"]:
            existing_tags = set((existing.tags or "").split(","))
            incoming_tags = set(incoming["tags"].split(","))
            merged = existing_tags | incoming_tags
            merged.discard("")
            existing.tags = ",".join(sorted(merged)) if merged else None

        existing.cloud_version = (existing.cloud_version or 0) + 1
        logger.info("Merged venue %s (cloud_version=%d)", existing.id, existing.cloud_version)

        return existing


venue_merge_service = VenueMergeService()
