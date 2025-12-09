#!/usr/bin/env python3
"""
Seed test users for E2E tests.

This script creates the test users in the database so that
e2e tests can submit solutions with those user sessions.
"""

import os
import sys
from datetime import datetime, timezone

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, UserDB

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://e2e:e2e@localhost:5432/omj_e2e")

# Test users - must match e2e/tests/utils/auth.ts TEST_USERS
# Note: UserDB only has google_sub, email, name, created_at, updated_at
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
]


def seed_users():
    """Create test users in the database."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        for user_data in TEST_USERS:
            # Check if user already exists
            existing = session.query(UserDB).filter_by(google_sub=user_data["google_sub"]).first()
            if existing:
                print(f"User {user_data['email']} already exists, skipping")
                continue

            # Create user
            user = UserDB(
                google_sub=user_data["google_sub"],
                email=user_data["email"],
                name=user_data["name"],
                created_at=datetime.now(timezone.utc),
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
