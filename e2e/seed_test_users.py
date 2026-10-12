#!/usr/bin/env python3
"""
Seed test users for E2E tests.

This script creates the test users in the database so that
e2e tests can submit solutions with those user sessions.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, UserDB

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://e2e:e2e@localhost:5432/omj_e2e")

# Test users - must match e2e/tests/utils/auth.ts TEST_USERS
# Google accounts of adults (birth_year 2000, active), so the age step and the
# parent-consent guard stay out of the way of the other specs. users.id equals
# the Google sub, like every account created before login accounts existed.
TEST_USERS = [
    {
        "google_sub": "test-user-sub-123",
        "email": "test-user@example.com",
        "name": "Test User",
    },
    {
        "google_sub": "test-user-sub-456",
        "email": "test-user-2@example.com",
        "name": "Test User 2",
    },
    {
        "google_sub": "test-admin-sub-789",
        "email": "test-admin@example.com",
        "name": "Test Admin",
    },
    {
        "google_sub": "test-restricted-sub-000",
        "email": "restricted@example.com",
        "name": "Restricted User",
    },
    # Rate-limited users (NOT in ALLOWED_EMAILS, subject to rate limits)
    {
        "google_sub": "test-ratelimit-sub-111",
        "email": "ratelimited@example.com",
        "name": "Rate Limited User",
    },
    {
        "google_sub": "test-ratelimit-sub-222",
        "email": "ratelimited2@example.com",
        "name": "Rate Limited User 2",
    },
    {
        "google_sub": "test-ratelimit-sub-333",
        "email": "ratelimited3@example.com",
        "name": "Rate Limited User 3",
    },
    {
        "google_sub": "test-ratelimit-sub-444",
        "email": "ratelimited4@example.com",
        "name": "Rate Limited User 4",
    },
    {
        "google_sub": "test-ratelimit-sub-555",
        "email": "ratelimited5@example.com",
        "name": "Rate Limited User 5",
    },
    {
        "google_sub": "test-ratelimit-sub-666",
        "email": "ratelimited6@example.com",
        "name": "Rate Limited User 6",
    },
]


def seed_users():
    """Create test users in the database."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        for user_data in TEST_USERS:
            # Check if user already exists
            existing = session.query(UserDB).filter_by(id=user_data["google_sub"]).first()
            if existing:
                print(f"User {user_data['email']} already exists, skipping")
                continue

            # Create user
            user = UserDB(
                id=user_data["google_sub"],
                google_sub=user_data["google_sub"],
                birth_year=2000,
                status="active",
                email=user_data["email"],
                name=user_data["name"],
                # Old enough not to count against RATE_LIMIT_NEW_USERS_PER_DAY,
                # which the registration spec needs for its new accounts
                created_at=datetime.now(timezone.utc) - timedelta(days=30),
            )
            session.add(user)
            print(f"Created test user: {user_data['email']}")

        session.commit()
        print("Test users seeded successfully!")
    except Exception as e:
        session.rollback()
        print(f"Error seeding users: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    seed_users()
