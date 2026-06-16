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
    format="[HackerOne MCP] %(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

BASE_URL = "https://api.hackerone.com/v1"


def get_auth() -> tuple:
    username = os.environ.get("HACKERONE_API_USERNAME", "")
    token = os.environ.get("HACKERONE_API_TOKEN", "")
    if not username or not token:
        logger.error("HACKERONE_API_USERNAME and HACKERONE_API_TOKEN must be set")
    return (username, token)


def get_headers() -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


class HackerOneClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(get_headers())
        username, token = get_auth()
        if username and token:
            self.session.auth = (username, token)
        else:
            logger.warning("HackerOne credentials not set — requests will fail")

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


def setup_mcp_server(client: HackerOneClient) -> FastMCP:
    mcp = FastMCP("hackerone-mcp")

    @mcp.tool()
    def list_programs(page: int = 1, per_page: int = 25) -> Dict[str, Any]:
        """List HackerOne programs the authenticated hacker can access."""
        logger.info(f"Listing HackerOne programs (page={page}, per_page={per_page})")
        result = client.get("/hackers/programs", params={"page[number]": page, "page[size]": per_page})
        if result.get("success"):
            logger.info("Programs listed successfully")
        else:
            logger.error("Failed to list programs")
        return result

    @mcp.tool()
    def get_program(handle: str) -> Dict[str, Any]:
        """Get details for a specific HackerOne program by handle."""
        logger.info(f"Fetching program details: {handle}")
        result = client.get(f"/hackers/programs/{handle}")
        if result.get("success"):
            logger.info("Program details retrieved")
        else:
            logger.error("Failed to retrieve program details")
        return result

    @mcp.tool()
    def list_reports(program_handle: str = "", page: int = 1, per_page: int = 25, state: str = "") -> Dict[str, Any]:
        """List reports (bug reports) for the authenticated hacker."""
        logger.info(f"Listing reports (program={program_handle}, page={page}, state={state})")
        params: Dict[str, Any] = {"page[number]": page, "page[size]": per_page}
        if program_handle:
            params["filter[program]"] = program_handle
        if state:
            params["filter[state]"] = state
        result = client.get("/hackers/reports", params=params)
        if result.get("success"):
            logger.info("Reports listed successfully")
        else:
            logger.error("Failed to list reports")
        return result

    @mcp.tool()
    def get_report(report_id: str) -> Dict[str, Any]:
        """Get details for a specific report."""
        logger.info(f"Fetching report details: {report_id}")
        result = client.get(f"/hackers/reports/{report_id}")
        if result.get("success"):
            logger.info("Report details retrieved")
        else:
            logger.error("Failed to retrieve report details")
        return result

    @mcp.tool()
    def list_payments(page: int = 1, per_page: int = 25) -> Dict[str, Any]:
        """List bounties and payments for the authenticated hacker."""
        logger.info(f"Listing payments (page={page})")
        params = {"page[number]": page, "page[size]": per_page}
        result = client.get("/hackers/payments", params=params)
        if result.get("success"):
            logger.info("Payments listed successfully")
        else:
            logger.error("Failed to list payments")
        return result

    @mcp.tool()
    def get_program_scope(handle: str) -> Dict[str, Any]:
        """Get structured scope (in-scope and out-of-scope assets) for a HackerOne program."""
        logger.info(f"Fetching program scope: {handle}")
        result = client.get(f"/hackers/programs/{handle}/structured_scopes")
        if result.get("success"):
            logger.info("Program scope retrieved")
        else:
            logger.error("Failed to retrieve program scope")
        return result

    @mcp.tool()
    def search_programs(query: str, page: int = 1, per_page: int = 25) -> Dict[str, Any]:
        """Search HackerOne programs by keyword (name, handle, or description)."""
        logger.info(f"Searching programs (query={query}, page={page}, per_page={per_page})")
        params: Dict[str, Any] = {"page[number]": page, "page[size]": per_page}
        if query:
            params["filter[search]"] = query
        result = client.get("/hackers/programs", params=params)
        if result.get("success"):
            logger.info("Programs searched successfully")
        else:
            logger.error("Failed to search programs")
        return result

    @mcp.tool()
    def health_check() -> Dict[str, Any]:
        """Verify HackerOne API connectivity and credentials."""
        logger.info("Running HackerOne health check")
        result = client.get("/hackers/programs", params={"page[size]": 1})
        if result.get("success"):
            logger.info("HackerOne API health check passed")
            return {"success": True, "connected": True, "api_version": "v1"}
        logger.error("HackerOne API health check failed")
        return {"success": False, "connected": False, "error": result.get("error", "unknown")}

    return mcp


def main():
    logger.info("Starting HackerOne MCP server")

    username, token = get_auth()
    if not username or not token:
        logger.warning("HACKERONE_API_USERNAME or HACKERONE_API_TOKEN not set — tools will fail")

    client = HackerOneClient()
    mcp = setup_mcp_server(client)
    logger.info("HackerOne MCP server ready")
    mcp.run()


if __name__ == "__main__":
    main()
