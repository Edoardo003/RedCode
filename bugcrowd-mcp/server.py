#!/usr/bin/env python3
import sys
import os
import logging
import json
from typing import Dict, Any, Optional

import requests

from mcp.server.fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="[Bugcrowd MCP] %(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.bugcrowd.com"
API_VERSION = "2024-10-31"


def get_auth() -> tuple:
    username = os.environ.get("BUGCROWD_API_USERNAME", "")
    password = os.environ.get("BUGCROWD_API_PASSWORD", "")
    if not username or not password:
        logger.error("BUGCROWD_API_USERNAME and BUGCROWD_API_PASSWORD must be set")
    return (username, password)


def get_headers() -> Dict[str, str]:
    return {
        "Accept": "application/vnd.bugcrowd+json",
        "Bugcrowd-Version": API_VERSION,
        "Content-Type": "application/json",
    }


def get_auth_header() -> Dict[str, str]:
    username, password = get_auth()
    if not username or not password:
        return {}
    return {"Authorization": f"Token {username}:{password}"}


class BugcrowdClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(get_headers())
        auth_hdr = get_auth_header()
        if auth_hdr:
            self.session.headers.update(auth_hdr)

    def _request(
        self, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        url = f"{BASE_URL}{path}"
        try:
            logger.debug(f"{method} {url}")
            response = self.session.request(method, url, params=params, json=json_data, timeout=60)
            response.raise_for_status()
            return {"success": True, "data": response.json()}
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            body = {}
            try:
                body = e.response.json()
            except Exception:
                pass
            return {"success": False, "error": str(e), "status_code": e.response.status_code, "body": body}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"success": False, "error": str(e)}

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(self, path: str, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self._request("POST", path, json_data=json_data)


def setup_mcp_server(client: BugcrowdClient) -> FastMCP:
    mcp = FastMCP("bugcrowd-mcp")

    @mcp.tool()
    def list_programs(page: int = 1, per_page: int = 25) -> Dict[str, Any]:
        """List Bugcrowd programs the authenticated user can access."""
        logger.info(f"Listing Bugcrowd programs (page={page}, per_page={per_page})")
        result = client.get("/programs", params={"page[offset]": (page - 1) * per_page, "page[limit]": per_page})
        if result.get("success"):
            logger.info("Programs listed successfully")
        else:
            logger.error("Failed to list programs")
        return result

    @mcp.tool()
    def get_program(program_id: str) -> Dict[str, Any]:
        """Get details for a specific Bugcrowd program."""
        logger.info(f"Fetching program details: {program_id}")
        result = client.get(f"/programs/{program_id}")
        if result.get("success"):
            logger.info("Program details retrieved")
        else:
            logger.error("Failed to retrieve program details")
        return result

    @mcp.tool()
    def list_submissions(program_id: str = "", page: int = 1, per_page: int = 25, status: str = "") -> Dict[str, Any]:
        """List submissions (bug reports) across accessible programs."""
        logger.info(f"Listing submissions (program={program_id}, page={page}, status={status})")
        params: Dict[str, Any] = {"page[offset]": (page - 1) * per_page, "page[limit]": per_page}
        if program_id:
            params["filter[program]"] = program_id
        if status:
            params["filter[status]"] = status
        result = client.get("/submissions", params=params)
        if result.get("success"):
            logger.info("Submissions listed successfully")
        else:
            logger.error("Failed to list submissions")
        return result

    @mcp.tool()
    def get_submission(submission_id: str) -> Dict[str, Any]:
        """Get details for a specific submission."""
        logger.info(f"Fetching submission details: {submission_id}")
        result = client.get(f"/submissions/{submission_id}")
        if result.get("success"):
            logger.info("Submission details retrieved")
        else:
            logger.error("Failed to retrieve submission details")
        return result

    @mcp.tool()
    def create_submission_comment(submission_id: str, body: str, visibility: str = "workspace") -> Dict[str, Any]:
        """Post a comment on a submission."""
        logger.info(f"Creating comment on submission {submission_id}")
        payload = {
            "data": {
                "type": "comment",
                "attributes": {
                    "body": body,
                    "visibility": visibility,
                },
            }
        }
        result = client.post(f"/submissions/{submission_id}/comments", json_data=payload)
        if result.get("success"):
            logger.info("Comment created successfully")
        else:
            logger.error("Failed to create comment")
        return result

    @mcp.tool()
    def get_submission_comments(submission_id: str, page: int = 1, per_page: int = 25) -> Dict[str, Any]:
        """List comments on a submission."""
        logger.info(f"Listing comments for submission {submission_id}")
        params = {"page[offset]": (page - 1) * per_page, "page[limit]": per_page}
        result = client.get(f"/submissions/{submission_id}/comments", params=params)
        if result.get("success"):
            logger.info("Comments listed successfully")
        else:
            logger.error("Failed to list comments")
        return result

    @mcp.tool()
    def list_monetary_rewards(page: int = 1, per_page: int = 25) -> Dict[str, Any]:
        """List monetary rewards for the authenticated user."""
        logger.info(f"Listing monetary rewards (page={page})")
        params = {"page[offset]": (page - 1) * per_page, "page[limit]": per_page}
        result = client.get("/monetary_rewards", params=params)
        if result.get("success"):
            logger.info("Rewards listed successfully")
        else:
            logger.error("Failed to list rewards")
        return result

    @mcp.tool()
    def get_organization(organization_id: str) -> Dict[str, Any]:
        """Get details for a Bugcrowd organization."""
        logger.info(f"Fetching organization: {organization_id}")
        result = client.get(f"/organizations/{organization_id}")
        if result.get("success"):
            logger.info("Organization details retrieved")
        else:
            logger.error("Failed to retrieve organization details")
        return result

    @mcp.tool()
    def list_targets(program_id: str, page: int = 1, per_page: int = 100) -> Dict[str, Any]:
        """List in-scope targets for a Bugcrowd program."""
        logger.info(f"Listing targets for program {program_id}")
        params = {"page[offset]": (page - 1) * per_page, "page[limit]": per_page}
        result = client.get(f"/programs/{program_id}/targets", params=params)
        if result.get("success"):
            logger.info("Targets listed successfully")
        else:
            logger.error("Failed to list targets")
        return result

    @mcp.tool()
    def health_check() -> Dict[str, Any]:
        """Verify Bugcrowd API connectivity and credentials."""
        logger.info("Running Bugcrowd health check")
        result = client.get("/programs", params={"page[limit]": 1})
        if result.get("success"):
            logger.info("Bugcrowd API health check passed")
            return {"success": True, "connected": True, "api_version": API_VERSION}
        logger.error("Bugcrowd API health check failed")
        return {"success": False, "connected": False, "error": result.get("error", "unknown")}

    return mcp


def main():
    logger.info("Starting Bugcrowd MCP server")

    username, password = get_auth()
    if not username or not password:
        logger.warning("BUGCROWD_API_USERNAME or BUGCROWD_API_PASSWORD not set — tools will fail")

    client = BugcrowdClient()
    mcp = setup_mcp_server(client)
    logger.info("Bugcrowd MCP server ready")
    mcp.run()


if __name__ == "__main__":
    main()
