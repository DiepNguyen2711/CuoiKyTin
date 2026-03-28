import os
from decimal import Decimal

import django


# Django bootstrap
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from hourskill_app.models import User, Video  # noqa: E402


def tc_from_duration(duration_seconds: int) -> int:
    """Compute TC price with rule: (duration_seconds + 30) // 60."""
    return (int(duration_seconds) + 30) // 60


def main() -> None:
    # Ensure owner user exists
    owner, created = User.objects.get_or_create(
        username="Diep",
        defaults={
            "email": "diep@example.com",
            "is_creator": True,
        },
    )

    # Set default password if new user, or if current password is different
    if created or not owner.check_password("123"):
        owner.set_password("123")
        owner.save(update_fields=["password"])

    # Keep creator flag enabled for this seed owner
    if not owner.is_creator:
        owner.is_creator = True
        owner.save(update_fields=["is_creator"])

    videos_data = [
        {
            "title": "Rèn luyện kỹ năng nói hay và trôi chảy",
            "file_url": "https://drive.google.com/file/d/16TILQzwVv4wN-MkL5a5L04klxL1eHUwq/preview",
            "duration_seconds": 580,
        },
        {
            "title": "Python tricks - Viết code chuyên nghiệp",
            "file_url": "https://drive.google.com/file/d/1GgGJ5vOMQSny7hEvDD4UJtW2z1A0JZBf/preview",
            "duration_seconds": 499,
        },
        {
            "title": "Hướng dẫn cài đặt PowerBI Desktop",
            "file_url": "https://drive.google.com/file/d/1AmcUGEZ7UQ6dM7xMcit5KKXBZnz0SYIX/preview",
            "duration_seconds": 465,
        },
    ]

    # Detect if price_tc is a real model field in this schema version
    has_price_field = any(field.name == "price_tc" for field in Video._meta.get_fields())

    for item in videos_data:
        defaults = {
            "creator": owner,
            "description": "Standalone seed video for home feed",
            "file_url": item["file_url"],
            "duration_seconds": item["duration_seconds"],
            "is_standalone": True,
            "is_active": True,
            "is_deleted": False,
        }

        # If schema still stores price_tc, set it during seed.
        if has_price_field:
            defaults["price_tc"] = Decimal(tc_from_duration(item["duration_seconds"]))

        Video.objects.update_or_create(
            title=item["title"],
            creator=owner,
            defaults=defaults,
        )

    print("Seed successful! 3 videos added to Home Page.")


if __name__ == "__main__":
    main()
