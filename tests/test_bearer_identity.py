"""Backward-compat shim tests."""

from webapp.bearer_identity import resolve_oauth_identity


def test_shim_delegates_to_oauth_user():
    assert resolve_oauth_identity("Bearer x", host=None, tenant=None, client=None) is None
