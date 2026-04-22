from datetime import datetime, timedelta
from src.db.models.user import User
from src.db.models.subscription import Subscription


class TestUserModel:
    def test_display_name_first_name(self):
        user = User(id=1, first_name="Иван")
        assert user.get_display_name() == "Иван"

    def test_display_name_username_fallback(self):
        user = User(id=1, first_name=None, username="ivan_test")
        assert user.get_display_name() == "@ivan_test"

    def test_display_name_id_fallback(self):
        user = User(id=42, first_name=None, username=None)
        assert user.get_display_name() == "42"

    def test_has_active_unlimited_subscription(self):
        user = User(id=1)
        sub = Subscription(
            id=1,
            user_id=1,
            plan="pro",
            status="active",
            seconds_limit=-1,
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        user.subscriptions = [sub]
        assert user.has_active_unlimited_subscription() is True

    def test_no_active_subscription(self):
        user = User(id=1)
        user.subscriptions = []
        assert user.has_active_unlimited_subscription() is False

    def test_expired_subscription_not_unlimited(self):
        user = User(id=1)
        sub = Subscription(
            id=1,
            user_id=1,
            plan="pro",
            status="active",
            seconds_limit=-1,
            started_at=datetime.utcnow() - timedelta(days=60),
            expires_at=datetime.utcnow() - timedelta(days=1),  # expired
        )
        user.subscriptions = [sub]
        assert user.has_active_unlimited_subscription() is False

    def test_basic_subscription_not_unlimited(self):
        user = User(id=1)
        sub = Subscription(
            id=1,
            user_id=1,
            plan="basic",
            status="active",
            seconds_limit=108000,  # not -1
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        user.subscriptions = [sub]
        assert user.has_active_unlimited_subscription() is False

    def test_cancelled_subscription_not_active(self):
        user = User(id=1)
        sub = Subscription(
            id=1,
            user_id=1,
            plan="pro",
            status="cancelled",
            seconds_limit=-1,
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        user.subscriptions = [sub]
        assert user.has_active_unlimited_subscription() is False
