#!/usr/bin/env python3
"""
FastGeo batch image processing demo.

Workflow:
  1. GET  DrillHole/Get — resolve drill hole name
  2. POST WorkflowJob/Create — create batch (status NotStart)
  3. POST WorkflowJob/RerunJob — start processing
  4. GET  WorkflowJob/Get — poll every 5s until terminal status
  5. GET  Image/GetDetailByRow — fetch OCR / row detail on success

Required API key roles: ProcessBatch, GetDrillhole (for drill hole name), GetImageRowData

Usage:
  export FASTGEO_API_KEY="your-key"
  export PROJECT_ID=145 PROSPECT_ID=35 DRILLHOLE_ID=626 WORKFLOW_ID=52 IMAGE_TYPE_ID=91
  python batch_process_demo.py

Optional env vars: FASTGEO_BASE_URL (default: production API), IMAGE_SUBTYPE_ID,
                   IMAGE_CATEGORY, IS_ONLY_NEW_IMAGES, POLL_INTERVAL_SEC, OUTPUT_FILE,
                   BATCH_NAME, DRILLHOLE_NAME
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import requests

DEFAULT_BASE_URL = "https://api-portal1.fastgeo.com.au"
POLL_INTERVAL_SEC = 5
TERMINAL_STATUSES = {3, 4, 5}  # Completed, Failed, Canceled
STATUS_LABELS = {
    1: "NotStart",
    2: "Running",
    3: "Completed",
    4: "Failed",
    5: "Canceled",
}


def env_int(name: str, required: bool = True) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        if required:
            print(f"Missing required environment variable: {name}", file=sys.stderr)
            sys.exit(1)
        return None
    return int(raw)


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.lower() in ("1", "true", "yes", "y")


class FastGeoClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": api_key,
                "Accept": "application/json",
            }
        )

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _check_abp_result(self, response: requests.Response) -> Any:
        if not response.ok:
            body = response.text.strip()
            if body:
                print(f"API HTTP {response.status_code}: {body}", file=sys.stderr)
            response.raise_for_status()

        payload = response.json()
        if not payload.get("success", True):
            error = payload.get("error") or {}
            message = error.get("message") or payload
            raise RuntimeError(f"API error: {message}")
        return payload.get("result", payload)

    def get_drillhole(self, drillhole_id: int) -> dict[str, Any]:
        response = self.session.get(
            self._url("/api/services/app/DrillHole/Get"),
            params={"Id": drillhole_id},
        )
        result = self._check_abp_result(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected DrillHole/Get response: {result!r}")
        return result

    def create_batch(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            self._url("/api/services/app/WorkflowJob/Create"),
            json=body,
            headers={"Content-Type": "application/json"},
        )
        result = self._check_abp_result(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected Create response: {result!r}")
        return result

    def start_batch(self, job_id: int) -> None:
        response = self.session.post(
            self._url("/api/services/app/WorkflowJob/RerunJob"),
            json={"id": job_id},
            headers={"Content-Type": "application/json"},
        )
        self._check_abp_result(response)

    def get_workflow_job(self, job_id: int) -> dict[str, Any]:
        response = self.session.get(
            self._url("/api/services/app/WorkflowJob/Get"),
            params={"Id": job_id},
        )
        result = self._check_abp_result(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected Get response: {result!r}")
        return result

    def get_detail_by_row(
        self,
        project_id: int,
        prospect_id: int | None,
        drill_hole_id: int | None,
        skip_count: int = 0,
        max_result_count: int = 1000,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "ProjectId": project_id,
            "skipCount": skip_count,
            "maxResultCount": max_result_count,
        }
        if prospect_id is not None:
            params["ProspectId"] = prospect_id
        if drill_hole_id is not None:
            params["DrillHoleId"] = drill_hole_id

        response = self.session.get(
            self._url("/api/services/app/Image/GetDetailByRow"),
            params=params,
        )
        result = self._check_abp_result(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected GetDetailByRow response: {result!r}")
        return result


def poll_until_terminal(
    client: FastGeoClient,
    job_id: int,
    interval_sec: float,
) -> dict[str, Any]:
    while True:
        job = client.get_workflow_job(job_id)
        status = job.get("status")
        label = STATUS_LABELS.get(status, str(status))
        total = job.get("totalImage")
        completed = job.get("totalCompleted")
        errors = job.get("totalErrors")
        print(
            f"  Job {job_id}: status={label} ({status}), "
            f"progress={completed}/{total}, errors={errors}"
        )

        if status in TERMINAL_STATUSES:
            return job

        time.sleep(interval_sec)


def resolve_batch_name(client: FastGeoClient, drillhole_id: int) -> str:
    override = os.environ.get("BATCH_NAME")
    if override:
        return override

    env_name = os.environ.get("DRILLHOLE_NAME")
    if env_name:
        return f"Process drillhole {env_name}"

    try:
        drillhole = client.get_drillhole(drillhole_id)
        name = drillhole.get("name")
        if name:
            return f"Process drillhole {name}"
    except requests.RequestException as exc:
        print(
            f"Warning: could not fetch drillhole name ({exc}); using ID in batch name.",
            file=sys.stderr,
        )

    return f"Process drillhole {drillhole_id}"


def build_batch_body(
    *,
    batch_name: str,
    project_id: int,
    prospect_id: int,
    drillhole_id: int,
    workflow_id: int,
    image_type_id: int,
    image_subtype_id: int | None,
    image_category: int | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": batch_name,
        "description": "Created by batch_process_demo.py",
        "projectId": project_id,
        "prospectId": prospect_id,
        "drillholeId": drillhole_id,
        "workflowId": workflow_id,
        "imageTypeId": image_type_id,
        "isOnlyNewImages": env_bool("IS_ONLY_NEW_IMAGES", default=False),
    }
    if image_subtype_id is not None:
        body["imageSubtypeId"] = image_subtype_id
    if image_category is not None:
        body["imageCategory"] = image_category
    return body


def main() -> None:
    api_key = os.environ.get("FASTGEO_API_KEY")
    if not api_key:
        print("Set FASTGEO_API_KEY environment variable.", file=sys.stderr)
        sys.exit(1)

    base_url = os.environ.get("FASTGEO_BASE_URL", DEFAULT_BASE_URL)
    project_id = env_int("PROJECT_ID")
    prospect_id = env_int("PROSPECT_ID")
    drillhole_id = env_int("DRILLHOLE_ID")
    workflow_id = env_int("WORKFLOW_ID")
    image_type_id = env_int("IMAGE_TYPE_ID")
    image_subtype_id = env_int("IMAGE_SUBTYPE_ID", required=False)
    image_category = env_int("IMAGE_CATEGORY", required=False)
    poll_interval = float(os.environ.get("POLL_INTERVAL_SEC", POLL_INTERVAL_SEC))
    output_file = os.environ.get("OUTPUT_FILE", "detail_by_row.json")

    print(f"Base URL: {base_url}")

    client = FastGeoClient(base_url, api_key)
    batch_body = build_batch_body(
        batch_name=resolve_batch_name(client, drillhole_id),
        project_id=project_id,
        prospect_id=prospect_id,
        drillhole_id=drillhole_id,
        workflow_id=workflow_id,
        image_type_id=image_type_id,
        image_subtype_id=image_subtype_id,
        image_category=image_category,
    )

    print(f"Batch name: {batch_body['name']}")

    print("Step 1: Create batch...")
    job = client.create_batch(batch_body)
    job_id = job["id"]
    print(
        f"  Created job id={job_id}, status={STATUS_LABELS.get(job.get('status'), job.get('status'))}"
    )

    print("Step 2: Start batch (RerunJob)...")
    client.start_batch(job_id)
    print("  Processing started.")

    print(f"Step 3: Polling every {poll_interval}s...")
    final_job = poll_until_terminal(client, job_id, poll_interval)
    final_status = final_job.get("status")

    if final_status != 3:
        print(
            f"Batch finished with status {STATUS_LABELS.get(final_status, final_status)}. "
            "Skipping GetDetailByRow.",
            file=sys.stderr,
        )
        if final_job.get("failedImageIds"):
            print(f"  Failed image IDs: {final_job['failedImageIds']}", file=sys.stderr)
        sys.exit(1)

    print("Step 4: GetDetailByRow...")
    detail = client.get_detail_by_row(
        project_id=final_job.get("projectId", project_id),
        prospect_id=final_job.get("prospectId", prospect_id),
        drill_hole_id=final_job.get("drillholeId", drillhole_id),
    )

    total_count = detail.get("totalCount", len(detail.get("items", [])))
    print(f"  Retrieved {total_count} row(s).")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(detail, f, indent=2, ensure_ascii=False)
    print(f"Saved to {output_file}")
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except requests.ConnectionError as exc:
        base_url = os.environ.get("FASTGEO_BASE_URL", DEFAULT_BASE_URL)
        print(
            f"Cannot connect to {base_url}.\n"
            "  - For production: unset FASTGEO_BASE_URL or omit it (default is production).\n"
            "  - For local dev: start the backend, then export FASTGEO_BASE_URL=http://localhost:8080",
            file=sys.stderr,
        )
        print(f"Details: {exc}", file=sys.stderr)
        sys.exit(1)
