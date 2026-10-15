"""Convert a keystore to BKS for Morphe's patcher.

morphe-desktop's own KeystoreImporter.ensureBks (verified upstream at
MorpheApp/morphe-desktop:src/main/kotlin/app/morphe/engine/util/KeystoreImporter.kt)
short-circuits when the source keystore is already BKS, and otherwise converts
it via BouncyCastle. The BC copy shaded into morphe-desktop-*-all.jar has lost
its jar signature, so the JVM's JceSecurity refuses to trust it as a security
provider ("JCE cannot authenticate the provider BC"). Converting once, up
front, with the JDK's own keytool plus an officially signed bcprov jar means
Morphe is never handed a non-BKS keystore and never has to load BC itself.
"""

from __future__ import annotations

import hashlib
import logging
import subprocess
from pathlib import Path

from scripts.utils.network import download_with_lock

logger = logging.getLogger(__name__)

# Pinned like bin/apksigner.jar in scripts/lib/checks.sh: exact version +
# SHA-256 of the officially signed Maven Central artifact.
_BCPROV_VERSION = "1.85.2"
_BCPROV_SHA256 = "986b0fb92ec10e0c66b43e036ce0077e6150cfaecd1db9fb92b56672e157afe5"
_BCPROV_URL = (
    f"https://repo1.maven.org/maven2/org/bouncycastle/bcprov-jdk18on/"
    f"{_BCPROV_VERSION}/bcprov-jdk18on-{_BCPROV_VERSION}.jar"
)

# Byte-sniffed magic headers, mirroring Morphe's own
# KeystoreConversionUtils.detectFromBytes in the same upstream file.
_BKS_HEADER_PREFIX = b"\x00\x00\x00"
_BKS_VERSIONS = (1, 2)
_JKS_MAGIC = b"\xfe\xed\xfe\xed"
_PKCS12_TAG = 0x30
_PKCS12_LENGTH_BYTES = (0x80, 0x81, 0x82, 0x83, 0x84)


def _is_bks(header: bytes) -> bool:
    return header[:3] == _BKS_HEADER_PREFIX and header[3] in _BKS_VERSIONS


def _detect_store_type(keystore: Path) -> str | None:
    """Sniff a keystore's format from its header, mirroring Morphe's detectFromBytes.

    Returns the keytool ``-srcstoretype`` value, or ``None`` if already BKS
    (caller should short-circuit) or unrecognized.
    """
    header = keystore.read_bytes()[:4]
    if len(header) < 4:
        return None
    if _is_bks(header):
        return "BKS"
    if header == _JKS_MAGIC:
        return "JKS"
    if header[0] == _PKCS12_TAG and header[1] in _PKCS12_LENGTH_BYTES:
        return "PKCS12"
    return None


def _ensure_bcprov(bin_dir: Path) -> Path:
    """Download and SHA-256-verify the official signed BouncyCastle provider jar."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    bcprov_jar = bin_dir / "bcprov.jar"
    if not download_with_lock(_BCPROV_URL, bcprov_jar, sha256=_BCPROV_SHA256):
        msg = "Failed to download/verify bcprov.jar"
        raise RuntimeError(msg)
    return bcprov_jar


def ensure_bks(
    keystore: Path,
    password: str,
    *,
    bin_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> Path:
    """Return a BKS-format keystore usable by Morphe, converting if necessary.

    If ``keystore`` is already BKS, returns it unchanged -- never round-trips
    a working keystore through conversion. Otherwise converts once into
    ``cache_dir/<sha256-of-source>.bks`` and reuses that on later calls. Every
    entry is migrated (not filtered by alias), so the converted keystore's
    aliases and key material are unchanged and signatures stay identical to
    the source keystore.
    """
    store_type = _detect_store_type(keystore)
    if store_type == "BKS":
        return keystore
    if store_type is None:
        msg = f"Unrecognized keystore format: {keystore} (expected BKS, PKCS12, or JKS)"
        raise ValueError(msg)

    cache_dir = cache_dir or Path(".cache/keystore")
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(keystore.read_bytes()).hexdigest()
    converted = cache_dir / f"{source_hash}.bks"
    if converted.exists():
        return converted

    bcprov_jar = _ensure_bcprov(bin_dir or Path("bin"))
    temp_output = converted.with_suffix(".bks.tmp")
    temp_output.unlink(missing_ok=True)

    cmd = [
        "keytool",
        "-importkeystore",
        "-srckeystore",
        str(keystore),
        "-srcstoretype",
        store_type,
        "-destkeystore",
        str(temp_output),
        "-deststoretype",
        "BKS",
        "-srcstorepass",
        password,
        "-deststorepass",
        password,
        "-destkeypass",
        password,
        "-providerpath",
        str(bcprov_jar),
        "-providerclass",
        "org.bouncycastle.jce.provider.BouncyCastleProvider",
        "-noprompt",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        temp_output.unlink(missing_ok=True)
        msg = f"keytool BKS conversion failed: {result.stderr}"
        raise RuntimeError(msg)

    temp_output.replace(converted)
    logger.info("Converted %s keystore to BKS: %s", store_type, converted)
    return converted
