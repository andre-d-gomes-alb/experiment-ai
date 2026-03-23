"""create_admin

Revision ID: 316d4b226d06
Revises: 149e8ac6043f
Create Date: 2025-12-15 16:39:28.397792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.core.config import settings
from app.core.security import hash_password


# revision identifiers, used by Alembic.
revision: str = '316d4b226d06'
down_revision: Union[str, Sequence[str], None] = '149e8ac6043f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    result = conn.execute(
        sa.text("SELECT 1 FROM users WHERE email = :email"),
        {"email": settings.ADMIN_EMAIL},
    ).first()

    if result:
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO users (email, hashed_password, role, is_active)
            VALUES (:email, :password, :role, true)
            """
        ),
        {
            "email": settings.ADMIN_EMAIL,
            "password": hash_password(settings.ADMIN_PASSWORD),
            "role": "ADMIN",
        },
    )

def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM users WHERE email = :email"),
        {"email": settings.ADMIN_EMAIL},
    )
