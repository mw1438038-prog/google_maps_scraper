from datetime import datetime

from extensions import db


class FreemiusWebhookEvent(db.Model):
    __tablename__ = "freemius_webhook_events"

    event_id = db.Column(
        db.String(255),
        primary_key=True,
    )

    event_type = db.Column(
        db.String(100),
        nullable=False,
    )

    received_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    processed_at = db.Column(
        db.DateTime,
        nullable=True,
    )
