from datetime import datetime

from extensions import db


class SearchHistory(db.Model):
    __tablename__ = "search_history"
    __table_args__ = (
        db.Index(
            "ix_search_history_user_created",
            "user_id",
            "created_at",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    search_id = db.Column(db.String(32), nullable=False, unique=True, index=True)
    country = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(150), nullable=False)
    keyword = db.Column(db.String(150), nullable=False)
    result_count = db.Column(db.Integer, nullable=False, default=0)
    results = db.Column(db.JSON, nullable=False, default=list)
    export_count = db.Column(db.Integer, nullable=False, default=0)
    exported_leads = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    last_exported_at = db.Column(db.DateTime, nullable=True)