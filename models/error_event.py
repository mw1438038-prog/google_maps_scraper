from datetime import datetime

from extensions import db


class ErrorEvent(db.Model):
    __tablename__ = "error_events"
    __table_args__ = (
        db.UniqueConstraint(
            "request_id",
            "fingerprint",
            name="uq_error_event_request_fingerprint",
        ),
        db.Index("ix_error_events_timestamp", "event_timestamp"),
        db.Index("ix_error_events_component", "component"),
        db.Index("ix_error_events_category", "category"),
        db.Index("ix_error_events_severity", "severity"),
        db.Index("ix_error_events_status", "http_status"),
        db.Index("ix_error_events_fingerprint", "fingerprint"),
        db.Index("ix_error_events_request_id", "request_id"),
        db.Index(
            "ix_error_events_component_timestamp",
            "component",
            "event_timestamp",
        ),
        db.Index(
            "ix_error_events_category_timestamp",
            "category",
            "event_timestamp",
        ),
        db.Index(
            "ix_error_events_severity_timestamp",
            "severity",
            "event_timestamp",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    severity = db.Column(db.String(16), nullable=False)
    component = db.Column(db.String(32), nullable=False)
    category = db.Column(db.String(48), nullable=False)
    route_template = db.Column(db.String(255), nullable=False)
    http_status = db.Column(db.Integer, nullable=True)
    request_id = db.Column(db.String(36), nullable=False)
    safe_summary = db.Column(db.String(240), nullable=False)
    exception_type = db.Column(db.String(100), nullable=True)
    fingerprint = db.Column(db.String(64), nullable=False)
    first_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    occurrence_count = db.Column(db.Integer, nullable=False, default=1)
