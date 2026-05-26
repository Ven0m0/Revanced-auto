"""Tests for scripts/scrapers/external_bundles.py."""

# ruff: noqa: S101

from __future__ import annotations

from unittest.mock import patch

import pytest

from scripts.scrapers.external_bundles import (
    BundleEntry,
    is_external_bundles_source,
    parse_bundle_selector,
    resolve_bundle,
)


class TestSourceDetection:
    def test_repo_slug_recognized(self) -> None:
        assert is_external_bundles_source("brosssh/revanced-external-bundles") is True

    def test_prefixed_form_recognized(self) -> None:
        assert is_external_bundles_source("external-bundles:revanced-patches") is True

    def test_other_sources_not_recognized(self) -> None:
        assert is_external_bundles_source("MorpheApp/morphe-patches") is False
        assert is_external_bundles_source("anddea/revanced-patches") is False

    def test_parse_selector_returns_none_for_repo_slug(self) -> None:
        assert parse_bundle_selector("brosssh/revanced-external-bundles") is None

    def test_parse_selector_extracts_bundle_type(self) -> None:
        assert parse_bundle_selector("external-bundles:revanced-patches") == "revanced-patches"

    def test_parse_selector_empty_returns_none(self) -> None:
        assert parse_bundle_selector("external-bundles:") is None


class TestResolveBundle:
    def test_returns_bundle_entry_from_graphql(self) -> None:
        fake = {
            "bundle": [
                {
                    "bundle_type": "revanced-patches",
                    "version": "5.0.0",
                    "download_url": "https://example.com/patches.jar",
                    "signature_download_url": "https://example.com/patches.jar.asc",
                },
            ],
        }
        with patch("scripts.scrapers.external_bundles._graphql_query", return_value=fake):
            entry = resolve_bundle("revanced-patches", "latest")
        assert isinstance(entry, BundleEntry)
        assert entry.version == "5.0.0"
        assert entry.download_url == "https://example.com/patches.jar"
        assert entry.signature_download_url == "https://example.com/patches.jar.asc"

    def test_specific_version_query(self) -> None:
        fake = {
            "bundle": [
                {
                    "bundle_type": "revanced-patches",
                    "version": "4.2.0",
                    "download_url": "https://example.com/patches.jar",
                    "signature_download_url": None,
                },
            ],
        }
        with patch("scripts.scrapers.external_bundles._graphql_query", return_value=fake) as mock:
            entry = resolve_bundle("revanced-patches", "4.2.0")
        assert entry.version == "4.2.0"
        assert entry.signature_download_url is None
        _, variables = mock.call_args.args
        assert variables == {"bundleType": "revanced-patches", "version": "4.2.0"}

    def test_missing_bundle_raises(self) -> None:
        with (
            patch("scripts.scrapers.external_bundles._graphql_query", return_value={"bundle": []}),
            pytest.raises(RuntimeError, match="no bundle found"),
        ):
            resolve_bundle("revanced-patches", "latest")

    def test_missing_download_url_raises(self) -> None:
        fake = {"bundle": [{"bundle_type": "x", "version": "1", "download_url": None}]}
        with (
            patch("scripts.scrapers.external_bundles._graphql_query", return_value=fake),
            pytest.raises(RuntimeError, match="no download_url"),
        ):
            resolve_bundle("x", "latest")
