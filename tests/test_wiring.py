"""Smoke test: the whole object graph assembles without touching the network.

Handler routers are module-level singletons (the aiogram idiom), so a
dispatcher can only be built once per process -- hence the module-scoped
fixture rather than building one per test.
"""

import pytest

from powerbank.bot.factory import create_dispatcher
from powerbank.bot.middlewares.access import AccessMiddleware
from powerbank.bot.middlewares.database import DatabaseMiddleware
from powerbank.bot.middlewares.user import UserMiddleware
from powerbank.core.config import Settings
from powerbank.db.session import create_engine, create_session_factory


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(BOT_TOKEN="111:TEST", DATABASE_URL="sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="module")
def dispatcher(settings):
    return create_dispatcher(settings, create_session_factory(create_engine(settings)))


def test_settings_available_to_handlers(dispatcher, settings):
    assert dispatcher["settings"] is settings


def test_middlewares_registered_in_order(dispatcher):
    ours = [
        m
        for m in dispatcher.update.outer_middleware
        if isinstance(m, DatabaseMiddleware | UserMiddleware | AccessMiddleware)
    ]
    # Order is load-bearing: user lookup needs the session, and the access gate
    # must come last so it sees a resolved user. Getting this wrong would let
    # non-members through, so it is asserted rather than assumed.
    assert [type(m) for m in ours] == [
        DatabaseMiddleware,
        UserMiddleware,
        AccessMiddleware,
    ]


def test_feature_routers_are_attached(dispatcher):
    root = dispatcher.sub_routers[0]
    assert {r.name for r in root.sub_routers} == {"admin", "start", "errors"}


def test_error_router_is_last(dispatcher):
    root = dispatcher.sub_routers[0]
    assert root.sub_routers[-1].name == "errors"


def test_resolved_update_types_include_messages(dispatcher):
    assert "message" in dispatcher.resolve_used_update_types()
