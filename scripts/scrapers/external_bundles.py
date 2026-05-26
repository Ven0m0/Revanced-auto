"""External-bundles aggregator client.

Resolves patch-bundle download URLs via the public GraphQL endpoint of
`brosssh/revanced-external-bundles`, a community-maintained metadata service.

The service does not host JARs itself; bundle entries carry a `download_url`
that points at the upstream publisher's artifact (typically a GitHub release).

This module is used when `patches-source` in `config.toml` is set to the
sentinel `brosssh/revanced-external-bundles` (or an explicit URL prefixed with
`external-bundles:`). For any other value, the regular GitHub release path
is used by the caller.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

EXTERNAL_BUNDLES_GRAPHQL_URL = "https://revanced-external-bundles.brosssh.com/hasura/v1/graphql"
EXTERNAL_BUNDLES_REPO_SLUG = "brosssh/revanced-external-bundles"
EXTERNAL_BUNDLES_URL_PREFIX = "external-bundles:"
HTTP_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class BundleEntry:
    """Resolved metadata for one external bundle."""

    bundle_type: str
    version: str
    download_url: str
    signature_download_url: str | None = None


def is_external_bundles_source(source: str) -> bool:
    """Return True if ``source`` should be resolved via the external-bundles API."""
    return source == EXTERNAL_BUNDLES_REPO_SLUG or source.startswith(EXTERNAL_BUNDLES_URL_PREFIX)


def parse_bundle_selector(source: str) -> str | None:
    """Extract the bundle_type selector from an ``external-bundles:<type>`` string.

    Returns None when no selector was given (caller should match by package).
    """
    if source.startswith(EXTERNAL_BUNDLES_URL_PREFIX):
        selector = source[len(EXTERNAL_BUNDLES_URL_PREFIX) :].strip()
        return selector or None
    return None


def _graphql_query(query: str, variables: dict[str, object] | None = None) -> dict[str, object]:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(  # noqa: S310 — fixed https endpoint
        EXTERNAL_BUNDLES_GRAPHQL_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310
            body = resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"external-bundles GraphQL request failed: {e}") from e

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"external-bundles GraphQL returned non-JSON: {e}") from e

    if "errors" in data:
        raise RuntimeError(f"external-bundles GraphQL errors: {data['errors']}")
    return data.get("data", {})


_BUNDLE_QUERY = """
query LatestBundle($bundleType: String, $version: String) {
  bundle(
    where: {
      _and: [
        {bundle_type: {_eq: $bundleType}},
        {version: {_eq: $version}}
      ]
    }
    order_by: {created_at: desc}
    limit: 1
  ) {
    bundle_type
    version
    download_url
    signature_download_url
  }
}
"""

_LATEST_BY_TYPE_QUERY = """
query LatestBundleByType($bundleType: String!) {
  bundle(
    where: {bundle_type: {_eq: $bundleType}, is_prerelease: {_eq: false}}
    order_by: {created_at: desc}
    limit: 1
  ) {
    bundle_type
    version
    download_url
    signature_download_url
  }
}
"""


def resolve_bundle(bundle_type: str, version: str = "latest") -> BundleEntry:
    """Look up a bundle by ``bundle_type`` and version (``latest`` for newest stable).

    Args:
        bundle_type: The aggregator's ``bundle_type`` selector (e.g. ``revanced-patches``).
        version: Version string or ``"latest"`` to pick the newest non-prerelease.

    Returns:
        A populated ``BundleEntry``.

    Raises:
        RuntimeError: When the API call fails or no bundle matches.
    """
    if version in {"latest", "dev", ""}:
        data = _graphql_query(_LATEST_BY_TYPE_QUERY, {"bundleType": bundle_type})
    else:
        data = _graphql_query(_BUNDLE_QUERY, {"bundleType": bundle_type, "version": version})

    bundles = data.get("bundle", []) if isinstance(data, dict) else []
    if not bundles:
        raise RuntimeError(
            f"external-bundles: no bundle found for type={bundle_type!r} version={version!r}",
        )

    entry = bundles[0]
    if not isinstance(entry, dict):
        raise TypeError(f"external-bundles: unexpected response shape: {entry!r}")

    download_url = entry.get("download_url")
    if not isinstance(download_url, str) or not download_url:
        raise RuntimeError(f"external-bundles: bundle has no download_url: {entry!r}")

    sig = entry.get("signature_download_url")
    return BundleEntry(
        bundle_type=str(entry.get("bundle_type", bundle_type)),
        version=str(entry.get("version", version)),
        download_url=download_url,
        signature_download_url=sig if isinstance(sig, str) and sig else None,
    )
