"""Backward-compatible shim — use ``oauth_user`` for new code."""

from __future__ import annotations

from typing import Optional

import httpx

from .oauth_user import AuthenticatedUser, resolve_authenticated_user


def is_meaningful_identity(value: Optional[str]) -> bool:
    if not value:
        return False
    return len(value.strip()) >= 2


def resolve_oauth_identity(
    authorization: str,
    *,
    host: Optional[str] = None,
    tenant: Optional[str] = None,
    client: Optional[httpx.Client] = None,
    timeout: Optional[httpx.Timeout] = None,
) -> Optional[str]:
    if not host or not tenant or client is None:
        return None
    user = resolve_authenticated_user(
        authorization,
        host=host,
        tenant=tenant,
        client=client,
        timeout=timeout,
    )
    return user.label


def identity_from_authorization(header_or_token: str) -> Optional[str]:
    from .oauth_user import extract_sub_from_authorization

    return extract_sub_from_authorization(header_or_token)


def resolve_identity_from_workers_me(
    host: str,
    tenant: str,
    authorization: str,
    *,
    client: httpx.Client,
    timeout: httpx.Timeout,
) -> Optional[str]:
    user = resolve_authenticated_user(
        authorization,
        host=host,
        tenant=tenant,
        client=client,
        timeout=timeout,
    )
    return user.label
