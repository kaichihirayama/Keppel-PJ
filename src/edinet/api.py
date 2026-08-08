"""Minimal EDINET API v2 client.

Only implements what Phase 1 needs to verify connectivity: listing
submitted documents for a given date. Document download / XBRL parsing
is added in later phases.

Reference: https://api.edinet-fsa.go.jp/ (EDINET API v2 specification).
The API key is never hardcoded; it is read from the EDINET_API_KEY
environment variable (.env).
"""
from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

EDINET_BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"

# EDINET doc type "120" = 有価証券報告書 (annual securities report).
DOC_TYPE_YUHO = "120"


class EdinetApiError(RuntimeError):
    """Raised when the EDINET API returns an unexpected response."""


def _get_api_key() -> str:
    api_key = os.getenv("EDINET_API_KEY")
    if not api_key:
        raise EdinetApiError(
            "EDINET_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    return api_key


def get_documents_list(target_date: date, doc_type: int = 2) -> dict[str, Any]:
    """Fetch the list of documents submitted on ``target_date``.

    ``doc_type=2`` requests full metadata (including document descriptions),
    per the EDINET API v2 spec.
    """
    api_key = _get_api_key()
    params = {
        "date": target_date.isoformat(),
        "type": doc_type,
        "Subscription-Key": api_key,
    }
    url = f"{EDINET_BASE_URL}/documents.json"

    logger.info("Requesting EDINET document list for %s", target_date)
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    status_code = payload.get("metadata", {}).get("status")
    if status_code and str(status_code) != "200":
        message = payload.get("metadata", {}).get("message", "unknown error")
        raise EdinetApiError(f"EDINET API returned status {status_code}: {message}")

    return payload


def filter_yuho_by_edinet_code(payload: dict[str, Any], edinet_code: str) -> list[dict[str, Any]]:
    """Filter a documents.json payload to 有価証券報告書 for one EDINET code."""
    results = payload.get("results", [])
    return [
        doc
        for doc in results
        if doc.get("edinetCode") == edinet_code and doc.get("docTypeCode") == DOC_TYPE_YUHO
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    today = date.today()
    data = get_documents_list(today)
    print(f"Documents submitted on {today}: {len(data.get('results', []))}")
