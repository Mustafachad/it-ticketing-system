from app import create_app, limiter, db as _db
from tests.conftest import make_user


def test_login_is_rate_limited():
    """After enough rapid attempts from the same client, the login route
    should start rejecting requests with 429 instead of continuing to check
    passwords - this is what actually slows down a brute-force attempt.

    Unlike the other tests, this one deliberately leaves rate limiting ON
    (the shared `client` fixture disables it via RATELIMIT_ENABLED=False so
    the rest of the suite can log in freely), so it builds its own app.
    """
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        # Deliberately omits LOGIN_RATE_LIMIT so it falls back to the default
        # "10 per minute" - a distinct limit string from the one the shared
        # `client`/`app` fixtures use, so their hit counters (which share the
        # same in-memory storage backend across every create_app() call in
        # this process) don't interfere with each other.
    })
    with app.app_context():
        make_user(_db, "rate_limit_target", "requester")

    client = app.test_client()
    responses = [
        client.post("/auth/login", data={"username": "rate_limit_target", "password": "wrong"})
        for _ in range(15)
    ]

    statuses = [r.status_code for r in responses]
    assert 429 in statuses, f"Expected a 429 after repeated attempts, got statuses: {statuses}"
    # The first several attempts should still be handled normally (200 = form
    # re-rendered with an "invalid password" flash), not immediately blocked.
    assert statuses[0] == 200


def test_rate_limiter_uses_moving_window_strategy():
    """Flask-Limiter's default is a *fixed* window - it counts requests per
    calendar-clock-aligned bucket (e.g. resets exactly at :00 of each minute),
    not a rolling 60 seconds from the first request. That has a real
    weakness: someone could send 9 requests at :59 and 9 more at :00 and get
    18 through in ~2 seconds, since each burst lands in a different bucket.

    This was caught during manual testing: clicks spread across several
    calendar minutes (4, 4, 10, then 7 per minute) never tripped the limiter,
    even though 25 total attempts were made well within a few minutes.

    We use "moving-window" instead, which tracks a true rolling window
    regardless of clock alignment. This test just confirms that
    configuration is actually in effect, rather than re-testing the timing
    behavior itself with real sleeps (which would be slow and flaky).
    """
    assert limiter._strategy == "moving-window"
