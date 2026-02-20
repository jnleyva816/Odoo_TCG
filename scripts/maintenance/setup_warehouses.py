#!/usr/bin/env python3
"""
Setup script to configure warehouse-based users.

This script:
1. Fetches warehouses from Odoo to get their IDs
2. Updates/creates users with correct warehouse assignments

Usage:
    cd /home/jleyva/Odoo_TCG
    source venv/bin/activate
    python scripts/setup_warehouses.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.auth.database import (  # noqa: E402
    get_user_by_username,
    init_db,
    update_user_warehouse,
    update_user_warehouse_ids,
)
from app.auth.service import get_auth_service  # noqa: E402
from app.services.odoo import get_odoo_service  # noqa: E402


async def main():
    print("🔧 Setting up warehouse-based user access...\n")

    # Initialize database
    await init_db()
    print("✅ Database initialized\n")

    # Connect to Odoo and get warehouses
    odoo = get_odoo_service()
    connected = await odoo.connect()
    if not connected:
        print("❌ Failed to connect to Odoo. Check your .env settings.")
        return

    print("✅ Connected to Odoo\n")

    # Fetch warehouses
    warehouses = await odoo.get_warehouses()
    print(f"📦 Found {len(warehouses)} warehouses:")
    for wh in warehouses:
        print(f"   - ID: {wh['id']}, Name: {wh['name']}, Code: {wh.get('code', 'N/A')}")

    print()

    # Find the specific warehouses
    josh_wh = None
    wren_wh = None
    for wh in warehouses:
        name = wh["name"].lower()
        if "josh" in name:
            josh_wh = wh
        elif "wren" in name:
            wren_wh = wh

    if not josh_wh:
        print("⚠️  Could not find Josh's warehouse. Please enter the warehouse ID manually:")
        print("   Available warehouses:", [f"{w['id']}: {w['name']}" for w in warehouses])
        josh_wh_id = int(input("Josh's warehouse ID: "))
        josh_wh = {"id": josh_wh_id, "name": "Manual"}
    else:
        josh_wh_id = josh_wh["id"]
        print(f"✅ Found Josh's warehouse: {josh_wh['name']} (ID: {josh_wh_id})")

    if not wren_wh:
        print("⚠️  Could not find Wren's warehouse. Please enter the warehouse ID manually:")
        print("   Available warehouses:", [f"{w['id']}: {w['name']}" for w in warehouses])
        wren_wh_id = int(input("Wren's warehouse ID: "))
        wren_wh = {"id": wren_wh_id, "name": "Manual"}
    else:
        wren_wh_id = wren_wh["id"]
        print(f"✅ Found Wren's warehouse: {wren_wh['name']} (ID: {wren_wh_id})")

    print()

    # Auth service
    auth = get_auth_service()
    await auth.initialize()

    # Update existing admin user (Josh) with access to both warehouses
    josh_user = await get_user_by_username("joshleyva816")  # Primary admin
    if not josh_user:
        # Try other common admin usernames
        for username in ["admin", "jleyva", "josh.leyva", "josh"]:
            josh_user = await get_user_by_username(username)
            if josh_user:
                break

    if josh_user:
        print(f"📝 Updating {josh_user['username']} with multi-warehouse access...")
        await update_user_warehouse(josh_user["id"], josh_wh_id)  # Default to Josh's warehouse
        await update_user_warehouse_ids(josh_user["id"], [josh_wh_id, wren_wh_id])  # Access to both
        print(f"   ✅ {josh_user['username']} can now access both warehouses")
    else:
        print("⚠️  Could not find admin user. You may need to set up warehouse access manually.")
        print("   Check the database for existing admin users.")

    print()

    # Create Wren user
    wren_user = await get_user_by_username("flemmian")
    if wren_user:
        print("📝 User 'flemmian' already exists. Updating warehouse assignment...")
        await update_user_warehouse(wren_user["id"], wren_wh_id)
        await update_user_warehouse_ids(wren_user["id"], [wren_wh_id])
        print("   ✅ Updated flemmian's warehouse")
    else:
        print("📝 Creating user 'flemmian' for Wren...")
        user_id = await auth.create_regular_user(
            username="flemmian",
            email="wren.fleming@gmail.com",
            password="Password1234!",  # pragma: allowlist secret
            warehouse_id=wren_wh_id,
        )
        print(
            f"   ✅ Created user 'flemmian' (ID: {user_id}) with warehouse: {wren_wh.get('name', wren_wh_id)}"
        )

    print()
    print("=" * 60)
    print("🎉 Setup complete!")
    print()
    print("User summary:")
    print("   - Admin (Josh): Has access to BOTH warehouses, can switch between them")
    print("   - flemmian (Wren): Only sees Wren's warehouse inventory")
    print()
    print("Login credentials for Wren:")
    print("   Username: flemmian")
    print("   Email: wren.fleming@gmail.com")
    print("   Password: Password1234!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
