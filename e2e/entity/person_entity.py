"""SQLAlchemy mapping for the persisted person directory record."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from e2e.entity.base import Base


class Person(Base):
    """A person row with unique email and optional contact phone."""

    __tablename__ = "persons"

    # The database enforces email uniqueness so concurrent creates cannot duplicate it.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
