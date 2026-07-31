#!/usr/bin/env python3
"""Fetch Skylab OpenAPI catalog endpoints with a Bearer access token.

Usage:
  export OC_ACCESS_TOKEN='eyJ...'   # raw JWT or full "Bearer eyJ..." value
  python scripts/skylab_openapi_check.py --host org.skylab.inday.io --tenant performance
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, Optional

import httpx

from webapp.service import _parse_openapi_catalog_response, _redacted_curl_get


def _normalize_token(raw: str) -> str:
    value = raw.strip()
    if not value.lower().startswith("bearer "):
        return f"Bearer {value}"
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Skylab OpenAPI catalog publication.")
    parser.add_argument("--host", default="org.skylab.inday.io")
    parser.add_argument("--tenant", default="performance")
    parser.add_argument("--token", default=os.environ.get("OC_ACCESS_TOKEN", ""))
    args = parser.parse_args()

    if not args.token.strip():
        print("Missing access token. Set OC_ACCESS_TOKEN or pass --token.", file=sys.stderr)
        return 2

    headers = {
        "Authorization": _normalize_token(args.token),
        "Accept": "application/json",
    }
    paths = [
        ("tenant_hub", f"/ccx/api/v1/{args.tenant}/openapi.json"),
        ("orgchart_public", f"/ccx/api/orgchart/v1/{args.tenant}/openapi.json"),
        ("orgchart_internal", f"/ccx/internalapi/orgchart/v1/{args.tenant}/openapi.json"),
    ]

    results = []
    with httpx.Client(timeout=30.0) as client:
        for name, path in paths:
            url = f"https://{args.host}{path}"
            resp = client.get(url, headers=headers)
            parsed = _parse_openapi_catalog_response(resp)
            item: Dict[str, Any] = {
                "name": name,
                "path": path,
                "url": url,
                "status": resp.status_code,
                "contentType": parsed["content_type"],
                "isOpenApiDocument": parsed["is_openapi_document"],
                "serviceTitle": parsed["service_title"],
                "serviceVersion": parsed["service_version"],
            }
            if not parsed["is_openapi_document"]:
                item["curlCommand"] = _redacted_curl_get(url)
            results.append(item)

    print(json.dumps({"host": args.host, "tenant": args.tenant, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
