from datetime import datetime

from extensions import db


class ComponentHealth(db.Model):
    __tablename__ = "component_health"

    component = db.Column(db.String(32), primary_key=True)
    status = db.Column(db.String(16), nullable=False, default="degraded")
    last_checked_at = db.Column(db.DateTime, nullable=True)
    last_success_at = db.Column(db.DateTime, nullable=True)
    last_failure_at = db.Column(db.DateTime, nullable=True)
    last_failure_event_id = db.Column(
        db.Integer,
        db.ForeignKey("error_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    check_source = db.Column(db.String(48), nullable=True)
    safe_status_detail = db.Column(db.String(240), nullable=True)
