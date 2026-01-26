#!/usr/bin/env python3
"""Test the /api/packages endpoint response"""
import sys
import os
sys.path.insert(0, os.getcwd())

from database import Database
import json

# Simulate Flask request
class FakeRequest:
    args = {'user_id': None}

db = Database()

# Test without user_id (what happens on profile page)
request = FakeRequest()

user_id_str = request.args.get('user_id')
user_id = int(user_id_str) if user_id_str else None

print("=== /api/packages API TEST ===\n")
print(f"user_id: {user_id}\n")

if user_id:
    packages = db.get_all_packages_progress(user_id)
    print("✅ Progress verisi hesaplandı")
else:
    packages = db.get_learning_packages()
    print("ℹ️ Sadece paket verisi (progress olmadan)")

print(f"\nToplam paket: {len(packages)}")
print("\nİlk 5 paket:")
for pkg in packages[:5]:
    print(f"  {json.dumps(pkg, indent=2, ensure_ascii=False)}")
    break

# Check if word_count exists
if packages:
    first = packages[0]
    print(f"\n✅ word_count mevcut: {'word_count' in first}")
    print(f"✅ word_count değeri: {first.get('word_count', 'YOK')}")

print("\n=== DONE ===")

