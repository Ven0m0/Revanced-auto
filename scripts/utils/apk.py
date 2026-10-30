"""APK operations module for signing, aligning, and merging split APKs."""

import logging
import re
import shutil
import subprocess
import zipfile
from enum import Enum
from pathlib import Path

from scripts.utils.java import JAVA_ARGS

logger = logging.getLogger(__name__)

# Pinned and SHA-verified by env_check.check_binaries.
APKSIGNER_JAR = Path("bin/apksigner.jar")


def _ensure_apksigner_jar() -> bool:
    """Fetch bin/apksigner.jar for local runs that skipped check-env, using env_check's pinned hash."""
    if APKSIGNER_JAR.exists():
        return True
    # Lazy import: env_check pulls in the network stack, which plain APK helpers do not need.
    from scripts.lib.env_check import fetch_pinned_binary

    return fetch_pinned_binary(APKSIGNER_JAR.name, APKSIGNER_JAR.parent)


class APKSigner:
    """APK signer with v1+v2 signature scheme enforcement."""

    def __init__(self, keystore: Path, keystore_password: str, key_alias: str, key_password: str) -> None:
        self.keystore = keystore
        self.keystore_password = keystore_password
        self.key_alias = key_alias
        self.key_password = key_password

    def sign(self, input_path: Path, output_path: Path) -> bool:
        if not _ensure_apksigner_jar():
            logger.error("%s is missing and could not be downloaded and SHA-256 verified", APKSIGNER_JAR)
            return False
        cmd = [
            "java",
            *JAVA_ARGS,
            "-jar",
            str(APKSIGNER_JAR),
            "sign",
            "--ks",
            str(self.keystore),
            "--ks-pass",
            f"pass:{self.keystore_password}",
            "--key-pass",
            f"pass:{self.key_password}",
            "--ks-key-alias",
            self.key_alias,
            "--v1-signing-enabled",
            "true",
            "--v2-signing-enabled",
            "true",
            "--v3-signing-enabled",
            "false",
            "--v4-signing-enabled",
            "false",
            "--out",
            str(output_path),
            str(input_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            # Never log cmd: it carries the pass: secrets.
            logger.error("apksigner failed (exit %s): %s", e.returncode, (e.stderr or "").strip())
            return False
        except OSError as e:
            logger.error("apksigner could not be started: %s", e)
            return False
        return True


def _validate_path(path: Path, base_dir: Path | None = None) -> bool:
    """Validate that a path does not contain path traversal attempts."""
    try:
        resolved = path.resolve()
        if base_dir is not None:
            base_resolved = base_dir.resolve()
            return str(resolved).startswith(str(base_resolved))
        return True
    except OSError, ValueError:
        return False


def _validate_apk_path(path: Path, purpose: str) -> None:
    """Validate APK file path and extension."""
    if not isinstance(path, Path):
        raise ValueError(f"{purpose}: path must be a Path object")
    if path.suffix.lower() != ".apk":
        raise ValueError(f"{purpose}: file must have .apk extension, got '{path.suffix}'")
    if not _validate_path(path):
        raise ValueError(f"{purpose}: path traversal detected in '{path}'")


def sign_apk(
    input_path: Path,
    output_path: Path,
    keystore: Path,
    keystore_password: str,
    key_alias: str,
    key_password: str,
) -> bool:
    """Sign APK with v1+v2 scheme enforcement."""
    _validate_apk_path(input_path, "sign_apk input")
    _validate_apk_path(output_path, "sign_apk output")

    if not keystore.exists():
        return False

    signer = APKSigner(keystore, keystore_password, key_alias, key_password)
    return signer.sign(input_path, output_path)


def align_apk(input_path: Path, output_path: Path) -> bool:
    """Zipalign APK to 4-byte alignment."""
    _validate_apk_path(input_path, "align_apk input")
    _validate_apk_path(output_path, "align_apk output")

    if not input_path.exists():
        return False

    cmd = ["zipalign", "-f", "-p", "4", str(input_path), str(output_path)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def signer_digests(apk_path: Path) -> set[str]:
    """Certificate SHA-256 digests (lowercase hex) of every signer; empty if the APK does not verify.

    A set, not one digest: key-rotated APKs (e.g. YouTube) list a new cert for newer Android and the
    original cert for older, and the original is the one sig.txt records.
    """
    _validate_apk_path(apk_path, "signer_digests")

    if not apk_path.exists() or not _ensure_apksigner_jar():
        return set()

    cmd = ["java", *JAVA_ARGS, "-jar", str(APKSIGNER_JAR), "verify", "--print-certs", str(apk_path)]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError, OSError:
        return set()

    # apksigner prints "Signer #1 certificate SHA-256 digest: <hex>" (or "Signer (minSdkVersion=..) ...").
    found = re.findall(r"certificate SHA-256 digest:\s*([A-Fa-f0-9:]+)", result.stdout + result.stderr)
    return {digest.replace(":", "").lower() for digest in found}


def load_signatures(path: Path = Path("assets/sig.txt")) -> dict[str, str]:
    """Map package name to expected stock certificate SHA-256 from ``<hex> <package>`` lines."""
    if not path.exists():
        return {}
    signatures: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            signatures[parts[1]] = parts[0].lower()
    return signatures


class BundleType(Enum):
    """Type of APK bundle."""

    APK = "apk"
    XAPK = "xapk"
    APKM = "apkm"
    UNKNOWN = "unknown"


def detect_bundle_type(file_path: Path) -> BundleType:
    """Detect the bundle type of a file."""
    if not file_path.exists():
        return BundleType.UNKNOWN

    suffix = file_path.suffix.lower()
    if suffix == ".apk":
        return BundleType.APK
    if suffix == ".xapk":
        return BundleType.XAPK
    if suffix == ".apkm":
        return BundleType.APKM

    try:
        with file_path.open("rb") as f:
            header = f.read(4)
        if header == b"PK\x03\x04":
            return BundleType.APK
    except OSError as e:
        logger.debug("Failed to read magic bytes from %s: %s", file_path, e)

    return BundleType.UNKNOWN


class SplitAPKHandler:
    """Handler for split APK bundles (XAPK, APKM)."""

    def detect_bundle_type(self, file_path: Path) -> BundleType:
        return detect_bundle_type(file_path)

    def _find_apkeditor(self) -> Path | None:
        candidates = [Path("bin/APKEditor.jar"), Path("APKEditor.jar")]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def merge_splits(self, bundle_path: Path, output_path: Path) -> bool:
        """Merge a split APK bundle into a single APK."""
        bundle_type = self.detect_bundle_type(bundle_path)
        if bundle_type == BundleType.APK:
            try:
                shutil.copy2(bundle_path, output_path)
                return True
            except OSError as e:
                logger.error("Failed to copy APK bundle: %s", e)
                return False
        if bundle_type in (BundleType.XAPK, BundleType.APKM):
            jar = self._find_apkeditor()
            if jar is None:
                return False
            try:
                subprocess.run(
                    ["java", *JAVA_ARGS, "-jar", str(jar), "merge", "-i", str(bundle_path), "-o", str(output_path)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return output_path.exists()
            except subprocess.CalledProcessError, OSError:
                return False
        return False

    def extract_splits(self, bundle_path: Path, output_dir: Path) -> list[Path]:
        """Extract split APKs from a bundle."""
        if not bundle_path.exists():
            return []

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            splits: list[Path] = []
            with zipfile.ZipFile(bundle_path, "r") as zf:
                names = zf.namelist()
                for name in names:
                    if not name.endswith(".apk"):
                        continue
                    if not _validate_path(output_dir / name, output_dir):
                        continue
                    dest = output_dir / Path(name).name
                    zf.extract(name, output_dir)
                    extracted = output_dir / name
                    if extracted != dest:
                        shutil.move(str(extracted), dest)
                    splits.append(dest)
            return splits
        except zipfile.BadZipFile, OSError:
            return []
