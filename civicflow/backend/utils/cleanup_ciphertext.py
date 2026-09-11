"""
Cleanup Ciphertext Values in user_profiles
============================================
Standalone script that scans MongoDB for ciphertext values
that leaked into profile fields without decryption.

Usage:
    python -m utils.cleanup_ciphertext          # dry-run (report only)
    python -m utils.cleanup_ciphertext --fix     # fix in place
    python -m utils.cleanup_ciphertext --csv     # export report to CSV
"""
import asyncio
import csv
import os
import re
import sys
from datetime import datetime
from typing import List, Dict, Tuple

# Add parent dir
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ciphertext detection pattern (same as field_validation.py)
_CIPHERTEXT_PATTERN = re.compile(r'^[A-Za-z0-9+/=]{12,}:[A-Za-z0-9+/=]{16,}$')
_PLAIN_PREFIX_PATTERN = re.compile(r'^plain:[A-Za-z0-9+/=]+$')


def is_ciphertext(value: str) -> bool:
    """Check if a value looks like AES-GCM ciphertext (nonce:cipher) or dev-mode encoded."""
    if not value or not isinstance(value, str):
        return False
    s = value.strip()
    return bool(_CIPHERTEXT_PATTERN.match(s) or _PLAIN_PREFIX_PATTERN.match(s))


async def scan_profiles(fix: bool = False, csv_path: str = None) -> List[Dict]:
    """
    Scan all user_profiles for ciphertext values.

    Returns list of affected records:
    [
        {
            "user_id": ...,
            "section": "basic_info",
            "field": "full_name",
            "raw_value_preview": "abc123:xyz...",
            "decryption_success": True/False,
            "decrypted_preview": "John Doe" or "",
            "fixed": True/False
        }
    ]
    """
    from dotenv import load_dotenv
    load_dotenv()

    from db.mongo import connect_mongo, get_db, close_mongo
    from config import settings

    mongo_uri = os.getenv("MONGO_URI", os.getenv("MONGODB_URI", ""))
    if not mongo_uri:
        print("ERROR: MONGO_URI not set in environment.")
        return []

    await connect_mongo(mongo_uri, settings.mongo_db_name)
    db = await get_db()
    if db is None:
        print("ERROR: Could not connect to MongoDB.")
        return []

    # Import encryption helpers
    try:
        from utils.encryption import (
            decrypt_dict_fields,
            ENCRYPTED_BASIC_FIELDS,
            ENCRYPTED_CONTACT_FIELDS,
            ENCRYPTED_IDENTITY_FIELDS,
        )
    except ImportError as e:
        print(f"ERROR: Could not import encryption utils: {e}")
        return []

    # Section → encrypted field names
    section_map = {
        "basic_info": ENCRYPTED_BASIC_FIELDS,
        "contact": ENCRYPTED_CONTACT_FIELDS,
        "identity": ENCRYPTED_IDENTITY_FIELDS,
    }

    results = []
    cursor = db.user_profiles.find({})
    total_profiles = 0
    affected_profiles = 0

    async for profile in cursor:
        total_profiles += 1
        user_id = profile.get("user_id", "unknown")
        profile_affected = False

        for section_name, encrypted_fields in section_map.items():
            section_data = profile.get(section_name, {})
            if not isinstance(section_data, dict):
                continue

            for field_name in encrypted_fields:
                raw_value = section_data.get(field_name, "")
                if not raw_value or not is_ciphertext(str(raw_value)):
                    continue

                # Found ciphertext! Try to decrypt
                profile_affected = True
                decryption_success = False
                decrypted_value = ""

                try:
                    decrypted = decrypt_dict_fields(
                        {field_name: raw_value},
                        user_id,
                        [field_name]
                    )
                    decrypted_value = decrypted.get(field_name, "")
                    decryption_success = bool(decrypted_value and not is_ciphertext(decrypted_value))
                except Exception as e:
                    print(f"  Decrypt error for {user_id}/{section_name}.{field_name}: {e}")

                record = {
                    "user_id": user_id,
                    "section": section_name,
                    "field": field_name,
                    "raw_value_preview": str(raw_value)[:60] + "...",
                    "decryption_success": decryption_success,
                    "decrypted_preview": str(decrypted_value)[:60] if decrypted_value else "",
                    "fixed": False,
                }

                print(f"  CIPHERTEXT: {user_id}/{section_name}.{field_name}")
                print(f"    Raw: {record['raw_value_preview']}")
                print(f"    Decrypt: {'OK' if decryption_success else 'FAILED'}")
                if decrypted_value:
                    print(f"    Decrypted: {record['decrypted_preview']}")

                # Fix in place if requested
                if fix and decryption_success and decrypted_value:
                    await db.user_profiles.update_one(
                        {"user_id": user_id},
                        {"$set": {f"{section_name}.{field_name}": decrypted_value}}
                    )
                    record["fixed"] = True
                    print(f"    FIXED: wrote decrypted value")
                elif fix and not decryption_success:
                    # Clear the ciphertext if we can't decrypt
                    await db.user_profiles.update_one(
                        {"user_id": user_id},
                        {"$set": {f"{section_name}.{field_name}": ""}}
                    )
                    record["fixed"] = True
                    print(f"    CLEARED: removed undecryptable ciphertext")

                results.append(record)

        if profile_affected:
            affected_profiles += 1

    print(f"\n{'='*60}")
    print(f"Scan complete: {total_profiles} profiles, {affected_profiles} affected, {len(results)} ciphertext fields")
    print(f"Mode: {'FIX' if fix else 'DRY RUN'}")
    print(f"{'='*60}")

    # Write CSV if requested
    if csv_path and results:
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"Report saved to: {csv_path}")

    await close_mongo()
    return results


async def main():
    fix = "--fix" in sys.argv
    csv_flag = "--csv" in sys.argv

    csv_path = None
    if csv_flag:
        csv_path = f"ciphertext_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    if fix:
        print("=" * 60)
        print("  WARNING: Running in FIX mode!")
        print("  This will modify user_profiles in MongoDB.")
        print("=" * 60)
        confirm = input("Type 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return

    results = await scan_profiles(fix=fix, csv_path=csv_path)

    if not results:
        print("\n✓ No ciphertext values found — profiles are clean.")
    else:
        print(f"\n✗ Found {len(results)} ciphertext field(s) across profiles.")
        if not fix:
            print("  Run with --fix to repair them.")


if __name__ == "__main__":
    asyncio.run(main())
