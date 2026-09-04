from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.storage.models import AuditEvent


async def append_audit_event(
    session: AsyncSession, order_id: UUID, event_type: str, payload: dict[str, Any]
) -> None:
    session.add(AuditEvent(order_id=order_id, event_type=event_type, payload=payload))

