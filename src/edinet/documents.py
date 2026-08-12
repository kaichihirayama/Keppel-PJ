"""Find and download specific EDINET documents.

EDINET's API only lists documents by submission date (documents.json), not
by company, so finding "the latest 有価証券報告書 for company X" means
scanning a date range and filtering by edinetCode + docTypeCode. This
module does that scan and downloads the matched document package.

Downloaded packages are saved under data/raw/documents/, separate from any
processed/extracted output (section 7 of the project instructions).
"""
from __future__ import annotations

import datetime as dt
import logging
import time
from pathlib import Path
from typing import Any

import requests

from src.edinet.api import DOC_TYPE_YUHO, EDINET_BASE_URL, EdinetApiError, _get_api_key, get_documents_list

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DOCUMENTS_DIR = PROJECT_ROOT / "data" / "raw" / "documents"

# type=1: 提出本文書及び監査報告書等一式 (zip containing XBRL/PDF/CSV).
DOCUMENT_PACKAGE_TYPE = 1


def find_documents_in_range(
    edinet_code: str,
    start_date: dt.date,
    end_date: dt.date,
    doc_type_code: str = DOC_TYPE_YUHO,
    request_interval_sec: float = 0.2,
) -> list[dict[str, Any]]:
    """Scan documents.json for each date in [start_date, end_date] and
    return the ones matching edinet_code/doc_type_code, most recent first.
    """
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")

    matches: list[dict[str, Any]] = []
    current = end_date
    while current >= start_date:
        try:
            payload = get_documents_list(current)
        except requests.HTTPError as exc:
            logger.warning("Failed to fetch document list for %s: %s", current, exc)
            current -= dt.timedelta(days=1)
            continue

        for doc in payload.get("results", []):
            if doc.get("edinetCode") == edinet_code and doc.get("docTypeCode") == doc_type_code:
                matches.append(doc)

        current -= dt.timedelta(days=1)
        if request_interval_sec:
            time.sleep(request_interval_sec)

    matches.sort(key=lambda d: d.get("submitDateTime", ""), reverse=True)
    return matches


# EDINET document download types (section: "書類取得API"):
#   1 = 提出本文書及び監査報告書等一式 (zip, contains XBRL/iXBRL)
#   2 = PDF (single .pdf file)
#   3 = 代替書面・添付文書 (zip)
#   4 = 英文ファイル (zip)
#   5 = CSV (zip)
_FILE_TYPE_EXTENSIONS = {1: "zip", 2: "pdf", 3: "zip", 4: "zip", 5: "zip"}


def download_document(
    doc_id: str,
    dest_dir: Path | None = None,
    file_type: int = DOCUMENT_PACKAGE_TYPE,
) -> Path:
    """Download a document package by docID. Skips the download if the
    destination file already exists (documents are not re-fetched, per
    section 7). Different file_type values are distinct files (e.g. the
    XBRL package vs. the PDF), so the filename encodes file_type.
    """
    api_key = _get_api_key()
    dest_dir = dest_dir or RAW_DOCUMENTS_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)
    extension = _FILE_TYPE_EXTENSIONS.get(file_type, "bin")
    dest_path = dest_dir / f"{doc_id}_type{file_type}.{extension}"

    if dest_path.exists():
        logger.info("Already downloaded: %s", dest_path)
        return dest_path

    url = f"{EDINET_BASE_URL}/documents/{doc_id}"
    params = {"type": file_type, "Subscription-Key": api_key}

    logger.info("Downloading document %s (type=%s) to %s", doc_id, file_type, dest_path)
    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    is_zip = "zip" in content_type or response.content.startswith(b"PK")
    is_pdf = "pdf" in content_type or response.content.startswith(b"%PDF")
    if extension == "zip" and not is_zip:
        raise EdinetApiError(
            f"Unexpected response downloading {doc_id} (content-type={content_type}): "
            f"{response.text[:300]}"
        )
    if extension == "pdf" and not is_pdf:
        raise EdinetApiError(
            f"Unexpected response downloading {doc_id} (content-type={content_type}): "
            f"{response.text[:300]}"
        )

    dest_path.write_bytes(response.content)
    return dest_path


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Find and download the latest 有価証券報告書")
    parser.add_argument("edinet_code")
    parser.add_argument("--start", default=None, help="YYYY-MM-DD, default: 400 days ago")
    parser.add_argument("--end", default=None, help="YYYY-MM-DD, default: today")
    args = parser.parse_args()

    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()
    start = dt.date.fromisoformat(args.start) if args.start else end - dt.timedelta(days=400)

    docs = find_documents_in_range(args.edinet_code, start, end)
    print(f"Found {len(docs)} matching document(s) between {start} and {end}.")
    for d in docs[:5]:
        print(f"  {d.get('docID')}  {d.get('submitDateTime')}  {d.get('docDescription')}")

    if docs:
        path = download_document(docs[0]["docID"])
        print(f"Downloaded latest to: {path}")
