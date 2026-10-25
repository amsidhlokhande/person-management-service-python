"""SQLAlchemy declarative metadata shared by all mapped entities."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class whose metadata is initialized by configured database clients."""

    pass
