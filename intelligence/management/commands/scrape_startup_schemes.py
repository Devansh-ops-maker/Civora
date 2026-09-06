import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
import requests

from intelligence.scrapers import get_startup_schemes


class Command(BaseCommand):
    help = "Scrape government schemes from Startup India and output structured JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            help="Optional file path to save the scraped schemes JSON.",
        )
        parser.add_argument(
            "--indent",
            type=int,
            default=2,
            help="Indentation for JSON output (default: 2).",
        )
        parser.add_argument(
            "--timeout",
            "-t",
            type=int,
            default=30,
            help="HTTP timeout in seconds (default: 30).",
        )

    def handle(self, *args, **options):
        output_path = options.get("output")
        indent = options.get("indent", 2)
        timeout = options.get("timeout", 30)

        self.stdout.write(self.style.NOTICE("Fetching schemes from Startup India..."))

        try:
            data = get_startup_schemes(timeout=timeout)
        except requests.RequestException as exc:
            raise CommandError(f"Failed to scrape Startup India schemes: {exc}") from exc
        except Exception as exc:
            raise CommandError(f"Unexpected error while scraping schemes: {exc}") from exc

        json_str = json.dumps(data, ensure_ascii=False, indent=indent)
        scheme_count = data.get("metadata", {}).get("scheme_count", len(data.get("schemes", [])))

        if output_path:
            file_path = Path(output_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json_str)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully scraped {scheme_count} schemes and saved to {file_path}"
                )
            )
        else:
            self.stdout.write(json_str)
