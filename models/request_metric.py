from datetime import datetime

from extensions import db


class RequestMetric(db.Model):
    __tablename__ = "request_metrics"
    __table_args__ = (
        db.Index("ix_request_metrics_timestamp", "event_timestamp"),
        db.Index("ix_request_metrics_request", "request_id"),
        db.Index("ix_request_metrics_route", "route_template"),
        db.Index("ix_request_metrics_status", "http_status"),
        db.Index("ix_request_metrics_outcome", "outcome"),
        db.Index("ix_request_metrics_component", "component"),
        db.Index("ix_request_metrics_outcome_timestamp", "outcome", "event_timestamp"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    request_id = db.Column(db.String(36), nullable=False)
    route_template = db.Column(db.String(255), nullable=False)
    http_status = db.Column(db.Integer, nullable=False)
    duration_ms = db.Column(db.Integer, nullable=False)
    outcome = db.Column(db.String(32), nullable=False)
    component = db.Column(db.String(32), nullable=False)
