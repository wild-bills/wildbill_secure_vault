import argparse
import csv
import os
import time
from dataclasses import dataclass
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_CSV = BASE_DIR / "gumroad_permalink_migration.csv"
DEFAULT_REPORT_CSV = BASE_DIR / "gumroad_permalink_migration_report.csv"
API_BASE = "https://api.gumroad.com/v2"


@dataclass
class RowResult:
    row_index: str
    current_permalink: str
    target_permalink: str
    status: str
    http_status: str
    message: str


def load_rows(input_csv: Path):
    if not input_csv.exists():
        raise FileNotFoundError(f"Missing CSV: {input_csv}")

    with input_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [row for row in reader]

    return rows


def prepare_updates(rows):
    updates = []
    for row in rows:
        status = str(row.get("status") or "").strip().lower()
        current = str(row.get("current_permalink") or "").strip()
        target = str(row.get("target_sku_permalink") or "").strip()

        if status != "needs_update":
            continue
        if not current or not target:
            continue
        if current == target:
            continue

        updates.append(row)

    return updates


def write_report(report_csv: Path, results):
    report_csv.parent.mkdir(parents=True, exist_ok=True)
    with report_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "row_index",
                "current_permalink",
                "target_permalink",
                "status",
                "http_status",
                "message",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "row_index": result.row_index,
                    "current_permalink": result.current_permalink,
                    "target_permalink": result.target_permalink,
                    "status": result.status,
                    "http_status": result.http_status,
                    "message": result.message,
                }
            )


def gumroad_update_permalink(access_token: str, current_permalink: str, target_permalink: str, timeout: int):
    endpoint = f"{API_BASE}/products/{current_permalink}"
    payload = {
        "access_token": access_token,
        "custom_permalink": target_permalink,
    }

    response = requests.put(endpoint, data=payload, timeout=timeout)

    # Retry with Bearer auth for tokens that are configured for header-based auth.
    if response.status_code == 401:
        bearer_response = requests.put(
            endpoint,
            json={"custom_permalink": target_permalink},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
        )
        response = bearer_response

    ok = response.status_code in (200, 201)

    message = ""
    try:
        body = response.json()
        message = str(body.get("message") or body.get("success") or "").strip()
    except Exception:
        message = response.text.strip()[:300]

    return ok, response.status_code, message


def gumroad_auth_preflight(access_token: str, timeout: int):
    """Validate API token and detect accepted auth mode before bulk updates."""
    endpoint = f"{API_BASE}/products"

    param_response = requests.get(endpoint, params={"access_token": access_token}, timeout=timeout)
    if param_response.status_code == 200:
        return True, "access_token_param", ""

    bearer_response = requests.get(
        endpoint,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=timeout,
    )
    if bearer_response.status_code == 200:
        return True, "bearer_header", ""

    message = ""
    param_msg = ""
    bearer_msg = ""

    try:
        payload = param_response.json()
        param_msg = str(payload.get("message") or payload).strip()
    except Exception:
        param_msg = (param_response.text or "").strip()[:200]

    try:
        payload = bearer_response.json()
        bearer_msg = str(payload.get("message") or payload).strip()
    except Exception:
        bearer_msg = (bearer_response.text or "").strip()[:200]

    message = (
        f"param_status={param_response.status_code}, bearer_status={bearer_response.status_code}; "
        f"param_msg={param_msg}; bearer_msg={bearer_msg}"
    )

    return False, "unknown", message


def run_migration(
    input_csv: Path,
    report_csv: Path,
    execute: bool,
    delay: float,
    timeout: int,
    limit: int | None,
    access_token_override: str,
):
    rows = load_rows(input_csv)
    updates = prepare_updates(rows)

    if limit is not None and limit > 0:
        updates = updates[:limit]

    print("Gumroad permalink migration runner")
    print("-" * 40)
    print(f"input rows:      {len(rows)}")
    print(f"update rows:     {len(updates)}")
    print(f"mode:            {'EXECUTE' if execute else 'DRY-RUN'}")

    if not updates:
        print("No updates to process.")
        write_report(report_csv, [])
        print(f"report:          {report_csv}")
        return 0

    access_token = str(access_token_override or os.environ.get("GUMROAD_ACCESS_TOKEN") or "").strip()
    if execute and not access_token:
        raise ValueError("GUMROAD_ACCESS_TOKEN is required when --execute is used")

    if execute:
        ok, mode, msg = gumroad_auth_preflight(access_token=access_token, timeout=timeout)
        if not ok:
            print("Authentication preflight failed before migration run.")
            if msg:
                print(f"API message: {msg}")
            print("No permalink updates were attempted.")
            return 1
        print(f"Auth preflight passed via: {mode}")

    results = []
    success_count = 0
    failed_count = 0

    for row in updates:
        row_index = str(row.get("row_index") or "")
        current = str(row.get("current_permalink") or "").strip()
        target = str(row.get("target_sku_permalink") or "").strip()

        if not execute:
            print(f"[DRY-RUN] row={row_index} {current} -> {target}")
            results.append(
                RowResult(
                    row_index=row_index,
                    current_permalink=current,
                    target_permalink=target,
                    status="dry_run",
                    http_status="",
                    message="Not executed",
                )
            )
            continue

        ok, status_code, message = gumroad_update_permalink(
            access_token=access_token,
            current_permalink=current,
            target_permalink=target,
            timeout=timeout,
        )

        if ok:
            success_count += 1
            status = "updated"
            print(f"[OK] row={row_index} {current} -> {target} (HTTP {status_code})")
        else:
            failed_count += 1
            status = "failed"
            print(f"[FAIL] row={row_index} {current} -> {target} (HTTP {status_code}) {message}")

        results.append(
            RowResult(
                row_index=row_index,
                current_permalink=current,
                target_permalink=target,
                status=status,
                http_status=str(status_code),
                message=message,
            )
        )

        if delay > 0:
            time.sleep(delay)

    write_report(report_csv, results)
    print("\nSummary")
    print("-" * 40)
    print(f"report:          {report_csv}")
    print(f"success:         {success_count}")
    print(f"failed:          {failed_count}")

    if execute and failed_count > 0:
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="Migrate Gumroad product permalinks from CSV")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_CSV, help="Input migration CSV")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_CSV, help="Output report CSV")
    parser.add_argument("--execute", action="store_true", help="Perform live Gumroad updates")
    parser.add_argument("--delay", type=float, default=0.35, help="Delay between API calls in seconds")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP timeout per request in seconds")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of rows to process (0 means no limit)")
    parser.add_argument("--access-token", default="", help="Optional Gumroad token override")
    args = parser.parse_args()

    limit = args.limit if args.limit > 0 else None
    exit_code = run_migration(
        input_csv=args.input,
        report_csv=args.report,
        execute=args.execute,
        delay=args.delay,
        timeout=args.timeout,
        limit=limit,
        access_token_override=str(args.access_token or "").strip(),
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
