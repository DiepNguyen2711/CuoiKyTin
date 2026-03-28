from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from hourskill_app.models import Category, Course, Video


class Command(BaseCommand):
    help = (
        "Normalize legacy course/video rows after moving to text categories and per-video pricing. "
        "Use --dry-run to preview changes before writing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to database.",
        )
        parser.add_argument(
            "--default-category",
            default="General",
            help="Fallback text category when both category_text and category FK are empty.",
        )
        parser.add_argument(
            "--clear-legacy-category-fk",
            action="store_true",
            help="Set Course.category to NULL after copying value to category_text.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        default_category = (options["default_category"] or "General").strip() or "General"
        clear_legacy_fk = options["clear_legacy_category_fk"]

        stats = {
            "courses_updated": 0,
            "videos_updated": 0,
            "category_text_fixed": 0,
            "legacy_category_fk_cleared": 0,
            "duration_fixed": 0,
            "base_price_fixed": 0,
            "base_price_clamped": 0,
        }

        with transaction.atomic():
            # Courses: normalize category_text so frontend/API never sees null/mismatched values.
            for course in Course.objects.select_related("category").all():
                changed_fields = []

                normalized_text = self._normalize_course_category_text(
                    course=course,
                    default_category=default_category,
                )

                if course.category_text != normalized_text:
                    course.category_text = normalized_text
                    changed_fields.append("category_text")
                    stats["category_text_fixed"] += 1

                if clear_legacy_fk and course.category_id is not None:
                    course.category_id = None
                    changed_fields.append("category")
                    stats["legacy_category_fk_cleared"] += 1

                if changed_fields:
                    stats["courses_updated"] += 1
                    if not dry_run:
                        course.save(update_fields=changed_fields)

            # Videos: normalize duration/base_price for per-video pricing compatibility.
            for video in Video.objects.all():
                changed_fields = []

                safe_duration = self._safe_duration(video.duration_seconds)
                if safe_duration != video.duration_seconds:
                    video.duration_seconds = safe_duration
                    changed_fields.append("duration_seconds")
                    stats["duration_fixed"] += 1

                safe_base_price, was_clamped = self._safe_base_price(video.base_price)
                if safe_base_price != video.base_price:
                    video.base_price = safe_base_price
                    changed_fields.append("base_price")
                    stats["base_price_fixed"] += 1
                if was_clamped:
                    stats["base_price_clamped"] += 1

                if changed_fields:
                    stats["videos_updated"] += 1
                    if not dry_run:
                        video.save(update_fields=changed_fields)

            if dry_run:
                transaction.set_rollback(True)

        mode = "DRY RUN" if dry_run else "APPLY"
        self.stdout.write(self.style.SUCCESS(f"[{mode}] Legacy data normalization finished."))
        self.stdout.write(f"Courses updated: {stats['courses_updated']}")
        self.stdout.write(f"  category_text fixed: {stats['category_text_fixed']}")
        self.stdout.write(f"  legacy category FK cleared: {stats['legacy_category_fk_cleared']}")
        self.stdout.write(f"Videos updated: {stats['videos_updated']}")
        self.stdout.write(f"  duration_seconds fixed: {stats['duration_fixed']}")
        self.stdout.write(f"  base_price fixed: {stats['base_price_fixed']}")
        self.stdout.write(f"  base_price clamped to >= 0: {stats['base_price_clamped']}")

        if dry_run:
            self.stdout.write(self.style.WARNING("No database changes were committed (--dry-run)."))

    def _normalize_course_category_text(self, course, default_category):
        raw = (course.category_text or "").strip()

        # Legacy payloads sometimes stored category id as string in category_text.
        if raw.isdigit():
            category_obj = Category.objects.filter(id=int(raw)).only("name").first()
            if category_obj:
                raw = category_obj.name

        if not raw and course.category_id and course.category:
            raw = (course.category.name or "").strip()

        if not raw:
            raw = default_category

        return raw[:120]

    def _safe_duration(self, duration_value):
        try:
            duration = int(duration_value or 0)
        except (TypeError, ValueError):
            return 0
        return max(0, duration)

    def _safe_base_price(self, base_price_value):
        try:
            safe = Decimal(str(base_price_value if base_price_value is not None else "0"))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal("0.00"), False

        was_clamped = safe < 0
        if was_clamped:
            safe = Decimal("0.00")

        return safe.quantize(Decimal("0.01")), was_clamped
