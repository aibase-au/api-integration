#!/usr/bin/env python
# -*- coding: utf-8 -*-
# coding: utf-8

"""
FastGeo full drill-hole batch processing.

Runs an entire drill hole through a workflow as a single batch job:
  1. GET  DrillHole/Get        — resolve drill hole name
  2. POST WorkflowJob/Create   — create batch (status NotStart)
  3. POST WorkflowJob/RerunJob — start processing
  4. GET  WorkflowJob/Get      — poll until a terminal status
  5. GET  Image/GetDetailByRow — fetch OCR / row detail on success

Configuration is read from the .env file (see README and authentication.py).
Authentication supports either API_KEY or USERNAME/PASSWORD.

Required API key roles: ProcessBatch, GetDrillhole, GetImageRowData.

Usage:
  python batch_process.py
"""

import json
import os
import sys
import time

import requests

from authentication import init_auth, authenticate, get_request_headers

DEFAULT_POLL_INTERVAL_SEC = 5
TERMINAL_STATUSES = {3, 4, 5}  # Completed, Failed, Canceled
STATUS_LABELS = {
    1: "NotStart",
    2: "Running",
    3: "Completed",
    4: "Failed",
    5: "Canceled",
}


def env_int(name, required=True):
    """Read an integer environment variable (loaded from .env by init_auth)."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        if required:
            print(f"Missing required environment variable: {name}", file=sys.stderr)
            sys.exit(1)
        return None
    return int(raw)


def env_bool(name, default=False):
    """Read a boolean environment variable (true/1/yes/y => True)."""
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "y")


class FastGeoClient:
    """Thin wrapper around the FastGeo API using the shared auth headers."""

    def __init__(self, api_endpoint, api_key, use_api_key, token=None):
        self.api_endpoint = api_endpoint.rstrip("/")
        self.api_key = api_key
        self.use_api_key = use_api_key
        self.token = token
        self.session = requests.Session()

    def _headers(self):
        return get_request_headers(
            self.api_key, self.use_api_key, self.api_endpoint, self.token
        )

    def _url(self, path):
        return f"{self.api_endpoint}{path}"

    def _check_abp_result(self, response):
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

    def get_drillhole(self, drillhole_id):
        response = self.session.get(
            self._url("/services/app/DrillHole/Get"),
            params={"Id": drillhole_id},
            headers=self._headers(),
        )
        result = self._check_abp_result(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected DrillHole/Get response: {result!r}")
        return result

    def create_batch(self, body):
        response = self.session.post(
            self._url("/services/app/WorkflowJob/Create"),
            json=body,
            headers=self._headers(),
        )
        result = self._check_abp_result(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected Create response: {result!r}")
        return result

    def start_batch(self, job_id):
        response = self.session.post(
            self._url("/services/app/WorkflowJob/RerunJob"),
            json={"id": job_id},
            headers=self._headers(),
        )
        self._check_abp_result(response)

    def get_workflow_job(self, job_id):
        response = self.session.get(
            self._url("/services/app/WorkflowJob/Get"),
            params={"Id": job_id},
            headers=self._headers(),
        )
        result = self._check_abp_result(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected Get response: {result!r}")
        return result

    def get_detail_by_row(
        self,
        project_id,
        prospect_id=None,
        drill_hole_id=None,
        skip_count=0,
        max_result_count=1000,
    ):
        params = {
            "ProjectId": project_id,
            "skipCount": skip_count,
            "maxResultCount": max_result_count,
        }
        if prospect_id is not None:
            params["ProspectId"] = prospect_id
        if drill_hole_id is not None:
            params["DrillHoleId"] = drill_hole_id

        response = self.session.get(
            self._url("/services/app/Image/GetDetailByRow"),
            params=params,
            headers=self._headers(),
        )
        result = self._check_abp_result(response)
        if not isinstance(result, dict):
            raise RuntimeError(f"Unexpected GetDetailByRow response: {result!r}")
        return result


def poll_until_terminal(client, job_id, interval_sec):
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


def resolve_batch_name(client, drillhole_id):
    override = os.getenv("BATCH_NAME")
    if override:
        return override

    env_name = os.getenv("DRILLHOLE_NAME")
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
    batch_name,
    project_id,
    prospect_id,
    drillhole_id,
    workflow_id,
    image_type_id,
    image_subtype_id,
    image_category,
):
    body = {
        "name": batch_name,
        "description": "Created by batch_process.py",
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


def main():
    # Load configuration and authentication from the .env file
    auth_config = init_auth()
    api_endpoint = auth_config["api_endpoint"]
    api_key = auth_config["api_key"]
    use_api_key = auth_config["use_api_key"]
    use_credentials = auth_config["use_credentials"]

    project_id = auth_config["projectId"]
    prospect_id = auth_config["prospectId"]
    workflow_id = auth_config["workflow_id"]

    # Validate the IDs that init_auth defaults to 0 / None
    if not project_id:
        print("Missing required environment variable: PROJECT_ID", file=sys.stderr)
        sys.exit(1)
    if not prospect_id:
        print("Missing required environment variable: PROSPECT_ID", file=sys.stderr)
        sys.exit(1)
    if not workflow_id:
        print("Missing required environment variable: WORKFLOW_ID", file=sys.stderr)
        sys.exit(1)

    drillhole_id = env_int("DRILLHOLE_ID")
    image_type_id = env_int("IMAGE_TYPE_ID")
    image_subtype_id = env_int("IMAGE_SUBTYPE_ID", required=False)
    image_category = env_int("IMAGE_CATEGORY", required=False)
    poll_interval = float(os.getenv("POLL_INTERVAL_SEC", DEFAULT_POLL_INTERVAL_SEC))
    output_file = os.getenv("OUTPUT_FILE", "detail_by_row.json")

    print(f"API endpoint: {api_endpoint}")

    # Resolve the authentication token (None when using an API key)
    token = authenticate(auth_config)
    if token is None and use_credentials:
        print("Authentication failed. Check your credentials in .env.", file=sys.stderr)
        sys.exit(1)

    client = FastGeoClient(api_endpoint, api_key, use_api_key, token)

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
        f"  Created job id={job_id}, "
        f"status={STATUS_LABELS.get(job.get('status'), job.get('status'))}"
    )

    print("Step 2: Start batch (RerunJob)...")
    client.start_batch(job_id)
    print("  Processing started.")

    print(f"Step 3: Polling every {poll_interval}s...")
    final_job = poll_until_terminal(client, job_id, poll_interval)
    final_status = final_job.get("status")

    if final_status != 3:
        print(
            f"Batch finished with status "
            f"{STATUS_LABELS.get(final_status, final_status)}. Skipping GetDetailByRow.",
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
        print(
            "Cannot connect to the API. Check API_ENDPOINT in your .env file "
            "(for local dev, start the backend and set API_ENDPOINT accordingly).",
            file=sys.stderr,
        )
        print(f"Details: {exc}", file=sys.stderr)
        sys.exit(1)
