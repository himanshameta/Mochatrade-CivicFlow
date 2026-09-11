"""
CivicFlow — Demo Seed Script
============================
Creates demo users, profile, documents, and sessions in MongoDB.
Run from the backend/ directory: python ../scripts/seed_demo.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / "backend" / ".env")

DEMO_EMAIL    = "demo@civicflow.in"
DEMO_PASSWORD = "Demo@1234"


async def seed():
    from db.mongo import connect_mongo, get_db
    from utils.auth import password_hash

    mongo_uri = os.getenv("MONGO_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    db_name   = os.getenv("DB_NAME", "civicflow")

    await connect_mongo(mongo_uri, db_name)
    db = await get_db()

    if db is None:
        print("❌  Could not connect to MongoDB. Check MONGODB_URI in .env")
        return

    user_id    = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    doc_id_1   = str(uuid.uuid4())
    doc_id_2   = str(uuid.uuid4())
    session_id_done   = str(uuid.uuid4())
    session_id_active = str(uuid.uuid4())
    now = datetime.utcnow()

    # ── 1. Demo User ──────────────────────────────────────────────────────
    existing = await db.users.find_one({"email": DEMO_EMAIL})
    if existing:
        print(f"⚠️  Demo user already exists (user_id={existing['user_id']}). Skipping user creation.")
        user_id = existing["user_id"]
    else:
        await db.users.insert_one({
            "user_id":       user_id,
            "email":         DEMO_EMAIL,
            "phone":         "9876543210",
            "password_hash": password_hash(DEMO_PASSWORD),
            "role":          "primary",
            "is_verified":   True,
            "created_at":    now,
            "last_login":    now,
            "telegram_chat_id": None,
        })
        print(f"✅  Created demo user → {DEMO_EMAIL} / {DEMO_PASSWORD}")

    # ── 2. User Profile ───────────────────────────────────────────────────
    await db.user_profiles.delete_many({"user_id": user_id})
    await db.user_profiles.insert_one({
        "profile_id": profile_id,
        "user_id":    user_id,
        "basic_info": {
            "full_name":    "Ramesh Kumar Demo",
            "dob":          "1990-05-15",
            "gender":       "M",
            "father_name":  "Suresh Kumar Demo",
        },
        "contact": {
            "address":      "123 Gandhi Nagar, Andheri West",
            "city":         "Mumbai",
            "state":        "Maharashtra",
            "pincode":      "400058",
            "phone":        "9876543210",
            "email":        DEMO_EMAIL,
        },
        "identity": {
            "aadhaar_last4": "7890",
            "pan_number":    "ABCDE1234F",
        },
        "uploaded_documents": [
            {
                "doc_id":          doc_id_1,
                "doc_type":        "aadhaar",
                "original_filename": "aadhaar.pdf",
                "storage_path":    f"./uploads/docs/{doc_id_1}.jpg",
                "ocr_extracted_fields": {
                    "full_name": "Ramesh Kumar Demo",
                    "dob":       "15/05/1990",
                    "gender":    "MALE",
                },
                "is_verified":     True,
            },
            {
                "doc_id":          doc_id_2,
                "doc_type":        "pan",
                "original_filename": "pan.jpg",
                "storage_path":    f"./uploads/docs/{doc_id_2}.jpg",
                "ocr_extracted_fields": {
                    "full_name":  "RAMESH KUMAR DEMO",
                    "pan_number": "ABCDE1234F",
                    "dob":        "15/05/1990",
                },
                "is_verified":     True,
            },
        ],
        "profile_completion": 75,
        "created_at": now,
        "updated_at": now,
    })
    print("✅  Created demo profile with 2 documents")

    # ── 3. Completed Form Session ─────────────────────────────────────────
    await db.form_sessions.delete_many({"user_id": user_id})
    await db.form_sessions.insert_one({
        "session_id": session_id_done,
        "user_id":    user_id,
        "url":        "https://passportindia.gov.in",
        "scraped_form": {
            "form_title": "Passport Application (Fresh)",
            "fields":     [],
        },
        "status":     "completed",
        "result":     "Application reference: PSP202412345",
        "conversation_history": [
            {"role": "assistant", "message": "I have started filling your passport form.", "timestamp": now - timedelta(hours=2)},
            {"role": "assistant", "message": "All fields filled successfully. Form submitted!", "timestamp": now - timedelta(hours=1)},
        ],
        "created_at": now - timedelta(days=3),
        "updated_at": now - timedelta(hours=1),
    })
    print("✅  Created completed form session")

    # ── 4. Active (correction_required) Session ───────────────────────────
    await db.form_sessions.insert_one({
        "session_id": session_id_active,
        "user_id":    user_id,
        "url":        "http://localhost:5001/anti-paste-form",
        "scraped_form": {
            "form_title": "Mock Anti-Paste Form",
            "fields": [
                {"field_id": "fullName", "label": "Full Name", "field_type": "text", "selector": "#name_field"},
                {"field_id": "address",  "label": "Address",   "field_type": "text", "selector": "#address_field"},
            ],
        },
        "status":      "paused_captcha",
        "pause_reason": "CAPTCHA detected on address field",
        "conversation_history": [
            {"role": "assistant", "message": "Started filling the form...", "timestamp": now - timedelta(minutes=10)},
            {"role": "assistant", "message": "⚠️ CAPTCHA detected. Waiting for you to solve it.", "timestamp": now - timedelta(minutes=5)},
        ],
        "data_requirements": [
            {"field_id": "fullName", "label": "Full Name", "value": "Ramesh Kumar Demo"},
            {"field_id": "address",  "label": "Address",   "value": "123 Gandhi Nagar, Andheri West"},
        ],
        "created_at": now - timedelta(minutes=15),
        "updated_at": now - timedelta(minutes=5),
    })
    print("✅  Created active (paused) form session")

    print("\n" + "=" * 50)
    print("  DEMO SEED COMPLETE")
    print("=" * 50)
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed())
