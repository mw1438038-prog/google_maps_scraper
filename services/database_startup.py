"""Database initialization rules for local and production deployments."""

from sqlalchemy import inspect

from extensions import db


def validate_production_schema():
    """Read-only check that the deployed schema matches ORM metadata."""
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    missing = []

    for table in db.metadata.sorted_tables:
        if table.name not in existing_tables:
            missing.append(f"missing table {table.name}")
            continue

        existing_columns = {
            column["name"]
            for column in inspector.get_columns(table.name)
        }
        for column in table.columns:
            if column.name not in existing_columns:
                missing.append(
                    f"missing column {table.name}.{column.name}"
                )

    if missing:
        raise RuntimeError(
            "Production database schema is not ready; apply the required "
            "SQL migration before deploying. "
            + "; ".join(missing)
        )


def initialize_database(app):
    """Create local schemas; validate production schemas without DDL."""
    with app.app_context():
        if (
            app.config.get("IS_PRODUCTION")
            or app.config.get("IS_VERCEL_RUNTIME")
        ):
            validate_production_schema()
            return

        db.create_all()
