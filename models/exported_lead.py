
from datetime import datetime

from extensions import db


class ExportedLead(db.Model):
    __tablename__ = "exported_leads"
    __table_args__ = (
        db.Index(
            "ix_exported_leads_user_created",
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

    place_id = db.Column(db.String(255), nullable=True)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.Text, nullable=True)

    phone = db.Column(db.String(100), nullable=True)
    website = db.Column(db.Text, nullable=True)
    email = db.Column(db.String(255), nullable=True)

    facebook = db.Column(db.Text, nullable=True)
    instagram = db.Column(db.Text, nullable=True)
    linkedin = db.Column(db.Text, nullable=True)
    twitter = db.Column(db.Text, nullable=True)
    other_social = db.Column(db.Text, nullable=True)

    rating = db.Column(db.Float, nullable=True)
    reviews = db.Column(db.Integer, nullable=True)
    maps_url = db.Column(db.Text, nullable=True)
    types = db.Column(db.JSON, nullable=True)

    country = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(150), nullable=True)
    keyword = db.Column(db.String(150), nullable=True)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
