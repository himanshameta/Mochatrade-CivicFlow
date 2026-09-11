"""
Profile Fields Migration Script
================================
Backfills new canonical fields into existing user_profiles documents:

1. Derives first_name, middle_name, last_name from full_name
2. Ensures city, state exist in contact section
3. Truncates full aadhaar numbers to last 4 digits
4. Reports affected profiles

Usage:
    cd backend
    python -m utils.migrate_profile_fields
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def migrate():
    from db.mongo import get_db
    from utils.profile_normalizer import split_full_name, truncate_aadhaar
    from utils.encryption import (
        decrypt_field,
        encrypt_field,
        ENCRYPTED_BASIC_FIELDS,
    )

    db = await get_db()
    if db is None:
        print("[Migration] ERROR: Could not connect to MongoDB")
        return

    cursor = db.user_profiles.find({})
    profiles = await cursor.to_list(length=10000)
    print(f"[Migration] Found {len(profiles)} profiles to check")

    updated = 0
    skipped = 0
    errors = 0

    for profile in profiles:
        user_id = profile.get("user_id", "unknown")
        update_ops = {}
        changes = []

        try:
            # ── 1. Name splitting ──
            basic_info = profile.get("basic_info", {})
            if isinstance(basic_info, dict):
                full_name_raw = basic_info.get("full_name", "")

                # Decrypt if encrypted
                full_name = full_name_raw
                if full_name and "full_name" in ENCRYPTED_BASIC_FIELDS:
                    try:
                        full_name = decrypt_field(full_name_raw, user_id)
                    except Exception:
                        full_name = full_name_raw  # May already be plaintext

                if full_name and full_name.strip():
                    parts = split_full_name(full_name)

                    # Only set if not already present
                    if not basic_info.get("first_name"):
                        if parts["first_name"]:
                            val = parts["first_name"]
                            if "first_name" in ENCRYPTED_BASIC_FIELDS:
                                val = encrypt_field(val, user_id)
                            update_ops["basic_info.first_name"] = val
                            changes.append(f"first_name={parts['first_name']}")

                    if not basic_info.get("middle_name"):
                        if parts["middle_name"]:
                            val = parts["middle_name"]
                            if "middle_name" in ENCRYPTED_BASIC_FIELDS:
                                val = encrypt_field(val, user_id)
                            update_ops["basic_info.middle_name"] = val
                            changes.append(f"middle_name={parts['middle_name']}")

                    if not basic_info.get("last_name"):
                        if parts["last_name"]:
                            val = parts["last_name"]
                            if "last_name" in ENCRYPTED_BASIC_FIELDS:
                                val = encrypt_field(val, user_id)
                            update_ops["basic_info.last_name"] = val
                            changes.append(f"last_name={parts['last_name']}")

                # Ensure father_name and mother_name fields exist
                if "father_name" not in basic_info:
                    update_ops["basic_info.father_name"] = ""
                if "mother_name" not in basic_info:
                    update_ops["basic_info.mother_name"] = ""

            # ── 2. Contact: ensure city, state, country ──
            contact = profile.get("contact", {})
            if isinstance(contact, dict):
                if "city" not in contact:
                    # Try to copy from basic_info
                    city = basic_info.get("city", "") if isinstance(basic_info, dict) else ""
                    update_ops["contact.city"] = city
                    if city:
                        changes.append(f"contact.city={city}")

                if "state" not in contact:
                    state = basic_info.get("state", "") if isinstance(basic_info, dict) else ""
                    update_ops["contact.state"] = state
                    if state:
                        changes.append(f"contact.state={state}")

                if "country" not in contact:
                    update_ops["contact.country"] = "India"

            # ── 3. Aadhaar truncation ──
            identity = profile.get("identity", {})
            if isinstance(identity, dict):
                aadhaar_raw = identity.get("aadhaar_last4", "")
                if aadhaar_raw:
                    # Decrypt if needed
                    aadhaar_plain = aadhaar_raw
                    try:
                        aadhaar_plain = decrypt_field(aadhaar_raw, user_id)
                    except Exception:
                        pass

                    # Check if it's more than 4 digits (full aadhaar stored)
                    digits = ''.join(c for c in str(aadhaar_plain) if c.isdigit())
                    if len(digits) > 4:
                        truncated = truncate_aadhaar(aadhaar_plain)
                        update_ops["identity.aadhaar_last4"] = truncated
                        changes.append(f"aadhaar truncated from {len(digits)} to {len(truncated)} digits")

            # ── Apply updates ──
            if update_ops:
                await db.user_profiles.update_one(
                    {"_id": profile["_id"]},
                    {"$set": update_ops}
                )
                updated += 1
                print(f"  [Migration] user={user_id}: {', '.join(changes) if changes else 'structural fields added'}")
            else:
                skipped += 1

        except Exception as e:
            errors += 1
            print(f"  [Migration] ERROR user={user_id}: {e}")

    print(f"\n[Migration] Complete: {updated} updated, {skipped} skipped, {errors} errors")


if __name__ == "__main__":
    print("[Migration] Starting profile fields migration...")
    asyncio.run(migrate())
    print("[Migration] Done.")
