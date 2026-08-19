"""Every model must be imported here so Alembic autogenerate can see it."""

from powerbank.db.base import Base
from powerbank.db.models.user import User

__all__ = ["Base", "User"]
