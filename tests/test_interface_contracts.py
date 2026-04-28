"""
Tests that mock and API clients for each integration share identical public method
signatures, enforced via abstract base classes.
"""
from __future__ import annotations

import inspect
from typing import get_type_hints

import pytest

from src.integrations.apollo.base import ApolloBase
from src.integrations.apollo.mock_client import ApolloMockClient
from src.integrations.apollo.api_client import ApolloAPIClient

from src.integrations.clay.base import ClayBase
from src.integrations.clay.mock_client import ClayMockClient
from src.integrations.clay.api_client import ClayAPIClient

from src.integrations.hubspot.base import HubSpotBase
from src.integrations.hubspot.mock_client import HubSpotMockClient
from src.integrations.hubspot.api_client import HubSpotAPIClient

from src.integrations.zerobounce.base import ZeroBounceBase
from src.integrations.zerobounce.mock_client import ZeroBounceMockClient
from src.integrations.zerobounce.api_client import ZeroBounceAPIClient

from src.integrations.neverbounce.base import NeverBounceBase
from src.integrations.neverbounce.mock_client import NeverBounceMockClient
from src.integrations.neverbounce.api_client import NeverBounceAPIClient

from src.integrations.validity.base import ValidityBase
from src.integrations.validity.mock_client import ValidityMockClient
from src.integrations.validity.api_client import ValidityAPIClient


def _public_methods(cls) -> set[str]:
    return {
        name for name, _ in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    }


def _sig_params(cls, method_name: str) -> list[str]:
    """Return parameter names (excluding 'self') for a method."""
    method = getattr(cls, method_name)
    sig = inspect.signature(method)
    return [p for p in sig.parameters if p != "self"]


def _assert_clients_match(base_cls, mock_cls, api_cls, integration: str):
    mock = mock_cls.__new__(mock_cls)
    api_cls_instance_check = api_cls

    # (a) Both are subclasses of the ABC
    assert issubclass(mock_cls, base_cls), (
        f"{integration}: {mock_cls.__name__} must subclass {base_cls.__name__}"
    )
    assert issubclass(api_cls, base_cls), (
        f"{integration}: {api_cls.__name__} must subclass {base_cls.__name__}"
    )

    # (b) Both clients expose the same set of public methods
    mock_methods = _public_methods(mock_cls)
    api_methods = _public_methods(api_cls)
    assert mock_methods == api_methods, (
        f"{integration}: method name mismatch — "
        f"mock has {mock_methods}, api has {api_methods}"
    )

    # (c) Both clients' method signatures match
    for method_name in mock_methods:
        mock_params = _sig_params(mock_cls, method_name)
        api_params = _sig_params(api_cls, method_name)
        assert mock_params == api_params, (
            f"{integration}.{method_name}: signature mismatch — "
            f"mock params={mock_params}, api params={api_params}"
        )


# ── Per-integration tests ─────────────────────────────────────────────────────

def test_apollo_mock_is_apollo_base():
    assert issubclass(ApolloMockClient, ApolloBase)


def test_apollo_api_is_apollo_base():
    assert issubclass(ApolloAPIClient, ApolloBase)


def test_apollo_signatures_match():
    _assert_clients_match(ApolloBase, ApolloMockClient, ApolloAPIClient, "Apollo")


def test_clay_mock_is_clay_base():
    assert issubclass(ClayMockClient, ClayBase)


def test_clay_api_is_clay_base():
    assert issubclass(ClayAPIClient, ClayBase)


def test_clay_signatures_match():
    _assert_clients_match(ClayBase, ClayMockClient, ClayAPIClient, "Clay")


def test_hubspot_mock_is_hubspot_base():
    assert issubclass(HubSpotMockClient, HubSpotBase)


def test_hubspot_api_is_hubspot_base():
    assert issubclass(HubSpotAPIClient, HubSpotBase)


def test_hubspot_signatures_match():
    _assert_clients_match(HubSpotBase, HubSpotMockClient, HubSpotAPIClient, "HubSpot")


def test_zerobounce_mock_is_zerobounce_base():
    assert issubclass(ZeroBounceMockClient, ZeroBounceBase)


def test_zerobounce_api_is_zerobounce_base():
    assert issubclass(ZeroBounceAPIClient, ZeroBounceBase)


def test_zerobounce_signatures_match():
    _assert_clients_match(ZeroBounceBase, ZeroBounceMockClient, ZeroBounceAPIClient, "ZeroBounce")


def test_neverbounce_mock_is_neverbounce_base():
    assert issubclass(NeverBounceMockClient, NeverBounceBase)


def test_neverbounce_api_is_neverbounce_base():
    assert issubclass(NeverBounceAPIClient, NeverBounceBase)


def test_neverbounce_signatures_match():
    _assert_clients_match(NeverBounceBase, NeverBounceMockClient, NeverBounceAPIClient, "NeverBounce")


def test_validity_mock_is_validity_base():
    assert issubclass(ValidityMockClient, ValidityBase)


def test_validity_api_is_validity_base():
    assert issubclass(ValidityAPIClient, ValidityBase)


def test_validity_signatures_match():
    _assert_clients_match(ValidityBase, ValidityMockClient, ValidityAPIClient, "Validity")
