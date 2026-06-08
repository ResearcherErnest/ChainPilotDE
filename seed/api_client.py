"""
HTTP client for the ChainPilot backend inventory API.

Wraps GET and POST calls to the backend REST API with consistent
error handling. Provides typed methods used by API-based seed scripts.
"""

import requests
from requests.exceptions import ConnectionError as ConnError, HTTPError, Timeout


class ApiClient:

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    # ── Internal helpers ─────────────────────────────────────────────

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except ConnError as exc:
            raise RuntimeError(f"Cannot connect to {url}: {exc}") from exc
        except Timeout:
            raise RuntimeError(f"Request timed out: {url}")
        except HTTPError as exc:
            raise RuntimeError(
                f"HTTP {exc.response.status_code} from {url}: {exc.response.text}"
            ) from exc

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = self._session.post(url, json=body, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except ConnError as exc:
            raise RuntimeError(f"Cannot connect to {url}: {exc}") from exc
        except Timeout:
            raise RuntimeError(f"Request timed out: {url}")
        except HTTPError as exc:
            raise RuntimeError(
                f"HTTP {exc.response.status_code} from {url}: {exc.response.text}"
            ) from exc

    # ── Typed API methods ────────────────────────────────────────────

    def get_categories(self) -> dict:
        """Return {name: id} for every category returned by GET /inventory/categories."""
        data = self._get("/inventory/categories")
        return {c["name"]: c["id"] for c in data}

    def get_uoms(self) -> dict:
        """Return {code: id} for every UOM returned by GET /inventory/units-of-measure."""
        data = self._get("/inventory/units-of-measure")
        return {u["code"]: u["id"] for u in data}

    def find_item_by_name(self, name: str) -> dict | None:
        """
        Search GET /inventory/items?search=<name> and return the first item whose
        displayName matches exactly. Returns None if not found.
        """
        data = self._get("/inventory/items", params={"search": name, "size": 10, "page": 0})
        for item in data.get("data") or []:
            if item.get("displayName") == name:
                return item
        return None

    def create_item(self, payload: dict) -> dict:
        """POST /inventory/items and return the created InventoryItemSummaryResponse."""
        return self._post("/inventory/items", payload)
