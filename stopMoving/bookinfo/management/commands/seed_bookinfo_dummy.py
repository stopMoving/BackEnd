from django.core.management.base import BaseCommand
from bookinfo.service import aladin_ingest

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--querytypes",
            nargs="*"
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Run without making changes to the database"
        )

    def handle(self, *args, **options):
        querytypes = options.get("querytypes")
        dry_run = options.get("dry_run", False)
        result = aladin_ingest.run(querytypes=querytypes, dry_run=dry_run)
        self.stdout.write(self.style.SUCCESS(
            "Done: "
                f"querytypes={result['querytypes']}, "
                f"isbn_collected={result['isbn_count']}, "
        ))