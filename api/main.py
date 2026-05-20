"""Async FastAPI service that runs Maigret username scans in the background
and sends results/status updates back to a Django backend via webhooks."""

import logging
import json
import os
import subprocess
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
import requests

app = FastAPI(title="OSINT Dashboard Async Engine")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_engine")


class ScanRequest(BaseModel):
    username: str = Field(..., min_length=1)
    search_id: int = Field(..., gt=0)

    @field_validator("username")
    @classmethod
    def prevent_empty_spaces(cls, value: str) -> str:
        """Extra security check to block strings that are just empty spaces."""

        if not value.strip():
            raise ValueError(
                "Username cannot be empty or contain only spaces."
            )
        return value


def run_maigret_cli_scan(username: str, search_id: int):
    """Executes Maigret via CLI and streams found accounts to Django webhooks."""

    logger.info(
        f"Starting background CLI scan for username: {username}"
    )

    report_filename = f"report_{username.lower()}.json"
    cmd = (
        f"maigret {username} --json simple --top-sites 100 "
        f"--no-progressbar"
    )

    try:
        requests.post(
            "http://127.0.0.1:8000/webhook/status/",
            json={"search_id": search_id, "status": "running"},
        )

        logger.info(f"Executing command: {cmd}")

        current_env = os.environ.copy()
        current_env["PYTHONIOENCODING"] = "utf-8"

        subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=current_env,
        )

        target_json_path = os.path.join(username, report_filename)

        if os.path.exists(target_json_path):
            logger.info(
                f"Report file located at {target_json_path}. "
                f"Commencing database transmission..."
            )

            with open(
                target_json_path, "r", encoding="utf-8"
            ) as f:
                scan_data = json.load(f)

            for site_name, profile_info in scan_data.items():
                if not isinstance(profile_info, dict):
                    continue

                status_obj = profile_info.get("status", {})

                is_found = (
                    profile_info.get("is_found")
                    or status_obj.get("is_found")
                    or status_obj.get("status") == "Claimed"
                )

                if is_found:
                    profile_url = (
                        profile_info.get("url_user")
                        or profile_info.get("url", "")
                    )

                    webhook_url = (
                        "http://127.0.0.1:8000/webhook/result/"
                    )
                    payload = {
                        "search_id": search_id,
                        "site_name": site_name,
                        "profile_url": profile_url,
                        "metadata": profile_info,
                    }

                    try:
                        response = requests.post(
                            webhook_url, json=payload, timeout=5
                        )
                        if response.status_code == 200:
                            logger.info(
                                f"Successfully broadcasted: "
                                f"{site_name} -> {profile_url}"
                            )
                        else:
                            logger.error(
                                "Django rejected webhook with "
                                f"status code: {response.status_code}"
                            )
                    except requests.exceptions.RequestException as e:
                        logger.error(
                            "Network error blasting webhook data "
                            f"for {site_name}: {e}"
                        )

        requests.post(
            "http://127.0.0.1:8000/webhook/status/",
            json={"search_id": search_id, "status": "completed"},
        )
        logger.info(
            f"CLI Scan completed successfully for {username}"
        )

    except subprocess.CalledProcessError as e:
        logger.error(f"Maigret CLI execution crashed: {e.stderr}")
        requests.post(
            "http://127.0.0.1:8000/webhook/status/",
            json={"search_id": search_id, "status": "failed"},
        )
    except Exception as e:
        logger.error(
            f"Background worker encountered an unhandled error: {str(e)}"
        )
        requests.post(
            "http://127.0.0.1:8000/webhook/status/",
            json={"search_id": search_id, "status": "failed"},
        )


@app.post("/scan/")
def start_scan(payload: ScanRequest, background_tasks: BackgroundTasks):
    """API endpoint triggered by Django to hand off an OSINT search task."""

    background_tasks.add_task(
        run_maigret_cli_scan, payload.username, payload.search_id
    )
    return {
        "message": (
            "Scan initiated in background via CLI execution"
        ),
        "target": payload.username,
    }
