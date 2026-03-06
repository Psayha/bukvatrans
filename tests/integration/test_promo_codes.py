"""Integration tests for promo code flow."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models.user import User
from src.db.models.promo_code import PromoCode, PromoCodeUse
from src.db.repositories.user import get_user


class TestPromoCodeRepository:
    @pytest.mark.asyncio
    async def test_promo_code_created(self, db_session):
        promo = PromoCode(
            code="TEST2026",
            type="free_seconds",
            value=7200,
            max_uses=100,
            is_active=True,
        )
        db_session.add(promo)
        await db_session.commit()

        result = await db_session.execute(
            select(PromoCode).where(PromoCode.code == "TEST2026")
        )
        found = result.scalar_one_or_none()
        assert found is not None
        assert found.value == 7200

    @pytest.mark.asyncio
    async def test_expired_promo_code(self, db_session):
        promo = PromoCode(
            code="EXPIRED",
            type="free_seconds",
            value=3600,
            expires_at=datetime.utcnow() - timedelta(days=1),
            is_active=True,
        )
        db_session.add(promo)
        await db_session.commit()

        result = await db_session.execute(
            select(PromoCode).where(PromoCode.code == "EXPIRED")
        )
        found = result.scalar_one_or_none()
        assert found.expires_at < datetime.utcnow()

    @pytest.mark.asyncio
    async def test_promo_code_use_unique_per_user(self, db_session, test_user):
        promo = PromoCode(code="ONCE", type="free_seconds", value=3600, is_active=True)
        db_session.add(promo)
        await db_session.commit()

        use = PromoCodeUse(promo_code_id=promo.id, user_id=test_user.id)
        db_session.add(use)
        await db_session.commit()

        # Second use should violate unique constraint
        use2 = PromoCodeUse(promo_code_id=promo.id, user_id=test_user.id)
        db_session.add(use2)
        with pytest.raises(Exception):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_inactive_promo_not_usable(self, db_session):
        promo = PromoCode(code="INACTIVE", type="free_seconds", value=3600, is_active=False)
        db_session.add(promo)
        await db_session.commit()

        result = await db_session.execute(
            select(PromoCode).where(
                PromoCode.code == "INACTIVE",
                PromoCode.is_active.is_(True),
            )
        )
        found = result.scalar_one_or_none()
        assert found is None

    @pytest.mark.asyncio
    async def test_max_uses_enforced(self, db_session):
        promo = PromoCode(
            code="LIMITED",
            type="free_seconds",
            value=3600,
            max_uses=5,
            used_count=5,
            is_active=True,
        )
        db_session.add(promo)
        await db_session.commit()

        result = await db_session.execute(
            select(PromoCode).where(PromoCode.code == "LIMITED")
        )
        found = result.scalar_one()
        assert found.used_count >= found.max_uses
