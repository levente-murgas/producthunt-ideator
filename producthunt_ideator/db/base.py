from sqlalchemy.orm import DeclarativeBase

from producthunt_ideator.db.meta import meta


class Base(DeclarativeBase):
    """Base for all models."""

    metadata = meta
