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
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.utils.network import download_with_lock

if TYPE_CHECKING:
    from collections.abc import Mapping

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

# Cache-key only, not credential storage; kept modest so each build pays ~tens of ms.
_PASSWORD_TAG_ITERATIONS = 100_000


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


def _convert(
    keystore: Path,
    password: str,
    *,
    src_type: str,
    dest_type: str,
    entry_password: str | None,
    alias: str | None,
    bin_dir: Path | None,
    cache_dir: Path | None,
) -> Path:
    """Convert ``keystore`` to ``dest_type`` via keytool + BouncyCastle, cached by source and mode."""
    key_password = entry_password or password
    single_entry: list[str] = []
    if key_password != password:
        if not alias:
            msg = "A keystore alias is required when the entry password differs from the store password"
            raise ValueError(msg)
        # keytool rejects -srckeypass on a whole-store import, so migrate only that entry.
        single_entry = ["-srcalias", alias, "-srckeypass", key_password]

    cache_dir = cache_dir or Path(".cache/keystore")
    cache_dir.mkdir(parents=True, exist_ok=True)
    # The mode (target type, alias, entry-password hash) is part of the key so a changed alias or
    # password never reuses a stale conversion; only hashes reach the filename.
    keystore_bytes = keystore.read_bytes()
    # PBKDF2 (not a bare SHA-256) so the password is never fast-hashed; salt is the keystore content.
    password_tag = hashlib.pbkdf2_hmac(
        "sha256", key_password.encode(), hashlib.sha256(keystore_bytes).digest(), _PASSWORD_TAG_ITERATIONS
    ).hex()
    mode = f"{dest_type}|{alias if single_entry else '*'}|{password_tag}"
    digest = hashlib.sha256(keystore_bytes + b"\0" + mode.encode()).hexdigest()
    converted = cache_dir / f"{digest}.{dest_type.lower()}"
    if converted.exists():
        return converted

    bcprov_jar = _ensure_bcprov(bin_dir or Path("bin"))
    # A per-call temp dir keeps parallel builds from racing on one shared temp file.
    temp_dir = Path(tempfile.mkdtemp(dir=cache_dir))
    temp_output = temp_dir / f"out.{dest_type.lower()}"

    cmd = [
        "keytool",
        "-importkeystore",
        "-srckeystore",
        str(keystore),
        "-srcstoretype",
        src_type,
        "-destkeystore",
        str(temp_output),
        "-deststoretype",
        dest_type,
        "-srcstorepass",
        password,
        "-deststorepass",
        password,
        *single_entry,
        "-destkeypass",
        key_password,
        "-providerpath",
        str(bcprov_jar),
        "-providerclass",
        "org.bouncycastle.jce.provider.BouncyCastleProvider",
        "-noprompt",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
        if result.returncode != 0:
            msg = f"keytool {dest_type} conversion failed: {result.stderr}"
            raise RuntimeError(msg)
        temp_output.replace(converted)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    logger.info("Converted %s keystore to %s: %s", src_type, dest_type, converted)
    return converted


def ensure_bks(
    keystore: Path,
    password: str,
    *,
    entry_password: str | None = None,
    alias: str | None = None,
    bin_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> Path:
    """Return a BKS-format keystore usable by Morphe, converting if necessary.

    If ``keystore`` is already BKS, returns it unchanged -- never round-trips
    a working keystore through conversion. Otherwise converts once into
    ``cache_dir`` and reuses that on later calls. When the entry password
    equals the store password every entry is migrated, so aliases and key
    material are unchanged and signatures stay identical to the source
    keystore. A distinct ``entry_password`` needs ``alias``: keytool rejects
    ``-srckeypass`` on a whole-store import ("if alias not specified,
    destalias and srckeypass must not be specified"), so only that entry is
    migrated, keeping its entry password.
    """
    store_type = _detect_store_type(keystore)
    if store_type == "BKS":
        return keystore
    if store_type is None:
        msg = f"Unrecognized keystore format: {keystore} (expected BKS, PKCS12, or JKS)"
        raise ValueError(msg)
    return _convert(
        keystore,
        password,
        src_type=store_type,
        dest_type="BKS",
        entry_password=entry_password,
        alias=alias,
        bin_dir=bin_dir,
        cache_dir=cache_dir,
    )


def ensure_jdk_readable(
    keystore: Path,
    password: str,
    *,
    entry_password: str | None = None,
    alias: str | None = None,
    bin_dir: Path | None = None,
    cache_dir: Path | None = None,
) -> Path:
    """Return a keystore apksigner can open with the JDK's default providers.

    PKCS12/JKS (and unrecognized files, left for apksigner to report) are returned unchanged.
    A BKS keystore is converted to PKCS12, or to JKS when the entry password differs from the
    store password, since keytool ignores ``-destkeypass`` for PKCS12 and would lose it.
    """
    if _detect_store_type(keystore) != "BKS":
        return keystore
    key_password = entry_password or password
    return _convert(
        keystore,
        password,
        src_type="BKS",
        dest_type="PKCS12" if key_password == password else "JKS",
        entry_password=entry_password,
        alias=alias,
        bin_dir=bin_dir,
        cache_dir=cache_dir,
    )


@dataclass(frozen=True, slots=True)
class SigningKeystore:
    """Credentials plus the two keystore copies a build signs with, resolved once per run.

    Both paths are None when no keystore is configured; the patcher then signs with its own
    default keystore and apksigner is skipped.
    """

    alias: str
    password: str
    entry_password: str
    patcher_keystore: Path | None = None
    apksigner_keystore: Path | None = None


def prepare_signing(
    keystore: Path | None,
    alias: str | None,
    environ: Mapping[str, str] = os.environ,
) -> SigningKeystore:
    """Resolve signing credentials and convert ``keystore`` for Morphe (BKS) and apksigner (JDK-readable).

    Default alias is lowercase "morphe": `keytool -genkeypair` always
    lowercases the alias it stores regardless of the case passed to
    `-alias` (confirmed: `keytool -list` on assets/ks.keystore, generated
    with `-alias Morphe`, shows the entry as "morphe"), and
    morphe-desktop's own alias lookup is exact-match, not the
    case-insensitive lookup java.security.KeyStore itself does --
    confirmed live: "Keystore does not contain entry with alias Morphe"
    even though standard KeyStore.getKey("Morphe", ...) resolves fine.
    Passwords come from KEYSTORE_PASSWORD/KEYSTORE_ENTRY_PASSWORD (already
    set by the CI workflows), so a real production keystore + secrets can
    override the defaults without a code change.
    """
    alias = alias or "morphe"
    password = environ.get("KEYSTORE_PASSWORD") or "Morphe"
    # An unset entry password means "same as the store password", the keytool/PKCS12 norm.
    entry_password = environ.get("KEYSTORE_ENTRY_PASSWORD") or password
    if keystore is None:
        return SigningKeystore(alias, password, entry_password)
    return SigningKeystore(
        alias,
        password,
        entry_password,
        patcher_keystore=ensure_bks(keystore, password, entry_password=entry_password, alias=alias),
        # apksigner only has the JDK's providers, which cannot read BKS.
        apksigner_keystore=ensure_jdk_readable(keystore, password, entry_password=entry_password, alias=alias),
    )
