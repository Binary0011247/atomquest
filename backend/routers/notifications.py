from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User
from notification_service import get_notifications_for_user, mark_all_read
from schemas import NotificationItem, NotificationListResponse, MessageResponse

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/my", response_model=NotificationListResponse)
def my_notifications(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    items = get_notifications_for_user(db, current_user)
    unread = sum(1 for i in items if not i.get("is_read"))
    return NotificationListResponse(
        notifications=[NotificationItem(**i) for i in items],
        unread_count=unread,
    )


@router.post("/mark-read", response_model=MessageResponse)
def mark_notifications_read(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    count = mark_all_read(db, current_user.id)
    return MessageResponse(message=f"Marked {count} notification(s) as read")
