#!/usr/bin/env python3
"""Startup India government schemes scraper.

Main method:
    get_startup_schemes()

It returns a JSON-serializable Python dict containing metadata and normalized
scheme records scraped from Startup India's public government-schemes data.
"""

from __future__ import annotations

import argparse
import json
import re
import warnings
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

SOURCE_PAGE_URL = "https://www.startupindia.gov.in/content/sih/en/government-schemes.html"
API_URL = "https://api.startupindia.gov.in/sih/api/noauth/search/getSearch?searchKey=allData"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.startupindia.gov.in",
    "Referer": SOURCE_PAGE_URL,
}

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _clean_list(value: Any) -> list[str]:
    if value in (None, "null", "undefined"):
        return []

    values = value if isinstance(value, list) else [value]
    cleaned = [_clean_text(item) for item in values]
    return [item for item in cleaned if item]


def _first(value: Any) -> str | None:
    cleaned = _clean_list(value)
    return cleaned[0] if cleaned else None


def _normalize_scheme(raw_scheme: dict[str, Any], source_group: str) -> dict[str, Any]:
    redirect_url = _first(raw_scheme.get("linktoApplication"))

    return {
        "id": _clean_text(raw_scheme.get("id")),
        "scheme_name": _first(raw_scheme.get("schname")),
        "ministry": _first(raw_scheme.get("mname")) or _first(raw_scheme.get("title")) or source_group,
        "source_group": source_group,
        "brief": _first(raw_scheme.get("brief")),
        "benefits": _clean_list(raw_scheme.get("benefits")),
        "benefit_tags": _clean_list(raw_scheme.get("benefitTags")),
        "eligibility_criteria": _clean_list(raw_scheme.get("EligibilityCriteria")),
        "quantum_size": _clean_list(raw_scheme.get("quantumSize")),
        "sectors": _clean_list(raw_scheme.get("sector")),
        "tenure": _clean_list(raw_scheme.get("tenure")),
        "notes": _first(raw_scheme.get("notes")),
        "application_url": redirect_url,
    }


class StartupIndiaScraper:
    """Scraper client for Startup India government schemes."""

    def __init__(
        self,
        api_url: str = API_URL,
        source_page_url: str = SOURCE_PAGE_URL,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        self.api_url = api_url
        self.source_page_url = source_page_url
        self.headers = headers or REQUEST_HEADERS
        self.timeout = timeout

    def fetch_raw_data(self) -> dict[str, Any]:
        """Fetch raw JSON data from the Startup India API."""
        response = requests.get(
            self.api_url,
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def parse_schemes(self, raw_payload: dict[str, Any]) -> dict[str, Any]:
        """Parse and normalize scheme data from raw API response payload."""
        data = raw_payload.get("data", {}) if isinstance(raw_payload, dict) else {}
        search_result = data.get("searchResult", {}) if isinstance(data, dict) else {}
        if not isinstance(search_result, dict):
            search_result = {}

        schemes: list[dict[str, Any]] = []
        for source_group, raw_schemes in search_result.items():
            for raw_scheme in raw_schemes or []:
                if isinstance(raw_scheme, dict):
                    schemes.append(_normalize_scheme(raw_scheme, source_group))

        schemes.sort(
            key=lambda scheme: (
                (scheme.get("ministry") or "").lower(),
                (scheme.get("scheme_name") or "").lower(),
            )
        )

        return {
            "metadata": {
                "source_page_url": self.source_page_url,
                "api_url": self.api_url,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "scheme_count": len(schemes),
                "group_count": len(search_result),
            },
            "schemes": schemes,
        }

    def scrape(self) -> dict[str, Any]:
        """Fetch and return parsed schemes."""
        raw_payload = self.fetch_raw_data()
        return self.parse_schemes(raw_payload)


def get_startup_schemes(timeout: int = 30) -> dict[str, Any]:
    """Scrape and return normalized Startup India government schemes."""
    scraper = StartupIndiaScraper(timeout=timeout)
    return scraper.scrape()


def get_startup_schemes_json(timeout: int = 30, indent: int = 2) -> str:
    """Return scraped Startup India schemes as a JSON string."""
    return json.dumps(get_startup_schemes(timeout=timeout), ensure_ascii=False, indent=indent)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Startup India government schemes.")
    parser.add_argument("--output", "-o", help="Optional JSON output file path.")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="HTTP request timeout in seconds (default: 30).")
    parser.add_argument("--indent", type=int, default=2, help="Indentation for JSON output (default: 2).")
    args = parser.parse_args()

    data = get_startup_schemes(timeout=args.timeout)
    json_data = json.dumps(data, ensure_ascii=False, indent=args.indent)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as file:
            file.write(json_data)
        print(f"Wrote {data['metadata']['scheme_count']} schemes to {args.output}")
    else:
        print(json_data)


if __name__ == "__main__":
    main()
