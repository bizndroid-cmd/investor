"""FastAPI alerts router for price alert CRUD operations.

Endpoints:
- GET /alerts — list all alerts for the current user
- POST /alerts — create a new alert
- PATCH /alerts/{alert_id} — update an existing alert
- DELETE /alerts/{alert_id} — delete an alert
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from backend.models.domain import (
    Alert,
    CreateAlertRequest,
    Session,
    UpdateAlertRequest,
)
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/alerts", tags=["alerts"])


def get_alert_service():
    """Dependency placeholder — overridden in main.py via app.dependency_overrides."""
    raise NotImplementedError("AlertService not wired. Use dependency overrides.")


@router.get("", response_model=list[Alert])
async def list_alerts(
    session: Session = Depends(get_current_user),
    alert_service=Depends(get_alert_service),
) -> list[Alert]:
    """Return all alerts (active and triggered) for the current user."""
    return await alert_service.get_alerts(session.user_id)


@router.post("", response_model=Alert, status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: CreateAlertRequest,
    session: Session = Depends(get_current_user),
    alert_service=Depends(get_alert_service),
) -> Alert:
    """Create a new price alert."""
    return await alert_service.create_alert(user_id=session.user_id, alert=body)


@router.patch("/{alert_id}", response_model=Alert)
async def update_alert(
    alert_id: UUID,
    body: UpdateAlertRequest,
    session: Session = Depends(get_current_user),
    alert_service=Depends(get_alert_service),
) -> Alert:
    """Partially update an existing alert."""
    return await alert_service.update_alert(
        user_id=session.user_id, alert_id=alert_id, update=body
    )


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: UUID,
    session: Session = Depends(get_current_user),
    alert_service=Depends(get_alert_service),
) -> Response:
    """Delete an alert by ID."""
    await alert_service.delete_alert(user_id=session.user_id, alert_id=alert_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
