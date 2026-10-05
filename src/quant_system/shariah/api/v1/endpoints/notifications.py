"""Endpoints for In-App Notifications, Web Push, and WhatsApp Alert Webhooks."""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import datetime

router = APIRouter(prefix="/notifications", tags=["Notifications & Alerts"])

class NotificationItem(BaseModel):
    id: str
    timestamp: str
    type: str  # COMPLIANCE_DRIFT, PURIFICATION_DUE, NISAB_UPDATE, MARKET_EVENT
    severity: str  # CRITICAL, WARNING, INFO
    title: str
    message: str
    ticker: Optional[str] = None
    is_read: bool = False
    action_url: Optional[str] = None

class WebhookAlertRequest(BaseModel):
    channel: str  # whatsapp, push
    recipient: str  # phone number or push subscription endpoint
    event_type: str
    ticker: Optional[str] = None
    message: str

# In-memory notification store pre-seeded with realistic Shariah alerts
_NOTIFICATIONS_STORE: List[NotificationItem] = [
    NotificationItem(
        id="notif-1",
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        type="COMPLIANCE_DRIFT",
        severity="WARNING",
        title="Compliance Drift Watch: TATAMOTORS.NS",
        message="Total interest-bearing debt has risen to 31.8% of Total Assets, nearing the 33% TASIS threshold.",
        ticker="TATAMOTORS.NS",
        is_read=False,
        action_url="/#portfolio"
    ),
    NotificationItem(
        id="notif-2",
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        type="PURIFICATION_DUE",
        severity="INFO",
        title="Dividend Declared: TCS.NS",
        message="Tata Consultancy Services declared ₹28.00/share dividend. Required purification: ₹0.42/share (1.5% impermissible income ratio).",
        ticker="TCS.NS",
        is_read=False,
        action_url="/#purification"
    ),
    NotificationItem(
        id="notif-3",
        timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        type="NISAB_UPDATE",
        severity="INFO",
        title="Silver Nisab Benchmark Updated",
        message="Current Indian Silver Nisab benchmark is calibrated at ₹53,550.00 (612.36g pure silver). Portfolios above this threshold require 2.5% Zakat.",
        ticker=None,
        is_read=False,
        action_url="/#zakat"
    )
]

@router.get("", response_model=List[NotificationItem], summary="Get User Notifications")
async def get_notifications():
    """Returns active in-app alerts (compliance drift, purification due, Nisab updates)."""
    return _NOTIFICATIONS_STORE

@router.post("/{notification_id}/read", summary="Mark Notification as Read")
async def mark_notification_read(notification_id: str):
    """Marks a notification as read."""
    for n in _NOTIFICATIONS_STORE:
        if n.id == notification_id:
            n.is_read = True
            return {"status": "success", "id": notification_id, "is_read": True}
    raise HTTPException(status_code=404, detail="Notification not found")

@router.post("/read-all", summary="Mark All Notifications as Read")
async def mark_all_read():
    """Marks all notifications as read."""
    for n in _NOTIFICATIONS_STORE:
        n.is_read = True
    return {"status": "success", "updated_count": len(_NOTIFICATIONS_STORE)}

@router.post("/webhook", summary="Simulate WhatsApp / Web Push Alert Dispatch")
async def dispatch_alert_webhook(payload: WebhookAlertRequest):
    """Dispatches a simulated real-time alert to WhatsApp or Browser Push."""
    return {
        "status": "dispatched",
        "channel": payload.channel,
        "recipient": payload.recipient,
        "event_type": payload.event_type,
        "delivered_at": datetime.datetime.now().isoformat(),
        "provider_response": f"Message queued successfully via {payload.channel.upper()} gateway."
    }
