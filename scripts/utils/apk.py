"""APK operations module for signing, aligning, and merging split APKs."""

import logging
import re
import shutil
import subprocess
import zipfile
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class APKSigner:
    """APK signer with v1+v2 signature scheme enforcement."""

    def __init__(self, keystore: Path, keystore_password: str, key_alias: str, key_password: str) -> None:
        self.keystore = keystore
        self.keystore_password = keystore_password
        self.key_alias = key_alias
        self.key_password = key_password

    def sign(self, input_path: Path, output_path: Path) -> bool:
        cmd = [
            "apksigner", "sign",
            "--ks", str(self.keystore),
            "--ks-pass", f"pass:{self.keystore_password}",
            "--key-pass", f"pass:{self.key_password}",
            "--ks-key-alias", self.key_alias,
            "--v1-signing-enabled", "true",
            "--v2-signing-enabled", "true",
            "--v3-signing-enabled", "false",
            "--v4-signing-enabled", "false",
            "--out", str(output_path),
            str(input_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False


def _validate_path(path: Path, base_dir: Path | None = None) -> bool:
    """Validate that a path does not contain path traversal attempts."""
    try:
        resolved = path.resolve()
        if base_dir is not None:
            base_resolved = base_dir.resolve()
            return str(resolved).startswith(str(base_resolved))
        return True
    except (OSError, ValueError):
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


def verify_signature(apk_path: Path) -> str | None:
    """Get APK signature SHA256 for verification."""
    _validate_apk_path(apk_path, "verify_signature")

    if not apk_path.exists():
        return None

    cmd = ["apksigner", "verify", "--print-certs", str(apk_path)]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        output = result.stdout + result.stderr

        sha256_match = re.search(r"SHA-256 fingerprint:\s*([A-Fa-f0-9:]+)", output)
        if sha256_match:
            fingerprint = sha256_match.group(1)
            return fingerprint.replace(":", "").lower()

        cert_match = re.search(r"Certificate [^ ]+ SHA-256:\s*([A-Fa-f0-9:]+)", output)
        if cert_match:
            fingerprint = cert_match.group(1)
            return fingerprint.replace(":", "").lower()

        return None
    except (subprocess.CalledProcessError, OSError):
        return None


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
                    ["java", "-jar", str(jar), "merge", "-i", str(bundle_path), "-o", str(output_path)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return output_path.exists()
            except (subprocess.CalledProcessError, OSError):
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
        except (zipfile.BadZipFile, OSError):
            return []


class AAPT2Manager:
    """Manager for downloading and using AAPT2 binaries for APK optimization."""

    SOURCES: list[str] = [
        "Graywizard888/Custom-Enhancify-aapt2-binary",
        "ReVanced-Extended-Organization/AAPT2",
    ]

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or Path.home() / ".cache" / "revanced" / "aapt2"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_aapt2(self, arch: str = "arm64-v8a") -> Path | None:
        from scripts.utils.network import gh_dl

        cached = self.cache_dir / f"aapt2-{arch}"
        if cached.exists():
            return cached

        for source in self.SOURCES:
            url = f"https://github.com/{source}/releases/latest/download/aapt2-{arch}"
            if gh_dl(cached, url):
                cached.chmod(0o755)
                return cached

        system_aapt2 = shutil.which("aapt2")
        if system_aapt2:
            return Path(system_aapt2)

        return None

    def optimize_apk(
        self,
        apk_path: Path,
        output_path: Path,
        *,
        arch: str = "arm64-v8a",
        languages: list[str] | None = None,
        densities: list[str] | None = None,
    ) -> bool:
        if not apk_path.exists():
            return False

        aapt2 = self.get_aapt2(arch)
        if aapt2 is None:
            return False

        cmd = [str(aapt2), "optimize", "-o", str(output_path), str(apk_path)]
        if languages:
            cmd += ["--target-locales", ",".join(languages)]
        if densities:
            cmd += ["--target-densities", ",".join(densities)]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return output_path.exists()
        except (subprocess.CalledProcessError, OSError):
            return False


def check_signature(apk_path: Path) -> bool:
    """Check if APK has valid v1+v2 signatures."""
    _validate_apk_path(apk_path, "check_signature")

    if not apk_path.exists():
        return False

    cmd = [
        "apksigner", "verify",
        "--v1-signing-enabled", "true",
        "--v2-signing-enabled", "true",
        "--v3-signing-enabled", "false",
        "--v4-signing-enabled", "false",
        str(apk_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False
