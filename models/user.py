from datetime import datetime

from extensions import db


class User(db.Model):
    __tablename__ = "users"

    # =====================================================
    # BASIC USER INFORMATION
    # =====================================================

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    google_id = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    name = db.Column(
        db.String(255),
        nullable=True
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    picture = db.Column(
        db.Text,
        nullable=True
    )

    # =====================================================
    # PLAN
    # =====================================================

    plan = db.Column(
        db.String(50),
        nullable=False,
        default="free"
    )

    # =====================================================
    # FREE TRIAL
    # =====================================================

    # True = Free trial already used
    # False = Free trial still available
    free_trial_used = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # =====================================================
    # SEARCH USAGE
    # =====================================================

    searches_used = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    searches_limit = db.Column(
        db.Integer,
        nullable=False,
        default=10
    )

    searches_reset_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    # =====================================================
    # SUBSCRIPTION
    # =====================================================

    subscription_status = db.Column(
        db.String(50),
        nullable=False,
        default="inactive"
    )

    subscription_started_at = db.Column(
        db.DateTime,
        nullable=True
    )

    subscription_expires_at = db.Column(
        db.DateTime,
        nullable=True
    )

    payment_provider = db.Column(
        db.String(50),
        nullable=True
    )

    payment_reference = db.Column(
        db.String(255),
        nullable=True
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    def __repr__(self):
        return f"<User {self.email}>"