"""APK operations module for signing, aligning, and merging split APKs."""

import re
import shutil
import subprocess
import tempfile
import zipfile
from enum import Enum
from pathlib import Path


class APKSigner:
    """APK signer with v1+v2 signature scheme enforcement."""

    def __init__(self, keystore: Path, keystore_password: str, key_alias: str, key_password: str) -> None:
        """Initialize APKSigner with keystore credentials.

        Args:
            keystore: Path to the keystore file.
            keystore_password: Password for the keystore.
            key_alias: Alias of the key to use for signing.
            key_password: Password for the key.
        """
        self.keystore = keystore
        self.keystore_password = keystore_password
        self.key_alias = key_alias
        self.key_password = key_password

    def sign(self, input_path: Path, output_path: Path) -> bool:
        """Sign an APK file with v1+v2 signature scheme.

        Args:
            input_path: Path to the input APK file.
            output_path: Path to the output signed APK file.

        Returns:
            True if signing succeeded, False otherwise.
        """
        cmd = [
            "apksigner",
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
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False


def _validate_path(path: Path, base_dir: Path | None = None) -> bool:
    """Validate that a path does not contain path traversal attempts.

    Args:
        path: The path to validate.
        base_dir: Optional base directory to check against.

    Returns:
        True if the path is safe, False otherwise.
    """
    try:
        resolved = path.resolve()
        if base_dir is not None:
            base_resolved = base_dir.resolve()
            return str(resolved).startswith(str(base_resolved))
        return True
    except (OSError, ValueError):
        return False


def _validate_apk_path(path: Path, purpose: str) -> None:
    """Validate APK file path and extension.

    Args:
        path: The path to validate.
        purpose: Description of the purpose for error messages.

    Raises:
        ValueError: If the path is invalid or has wrong extension.
    """
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
    """Sign APK with v1+v2 scheme enforcement.

    Args:
        input_path: Path to the input APK file.
        output_path: Path to the output signed APK file.
        keystore: Path to the keystore file.
        keystore_password: Password for the keystore.
        key_alias: Alias of the key to use for signing.
        key_password: Password for the key.

    Returns:
        True if signing succeeded, False otherwise.
    """
    _validate_apk_path(input_path, "sign_apk input")
    _validate_apk_path(output_path, "sign_apk output")

    if not keystore.exists():
        return False

    signer = APKSigner(keystore, keystore_password, key_alias, key_password)
    return signer.sign(input_path, output_path)


def align_apk(input_path: Path, output_path: Path) -> bool:
    """Zipalign APK to 4-byte alignment.

    Args:
        input_path: Path to the input APK file.
        output_path: Path to the output aligned APK file.

    Returns:
        True if alignment succeeded, False otherwise.
    """
    _validate_apk_path(input_path, "align_apk input")
    _validate_apk_path(output_path, "align_apk output")

    if not input_path.exists():
        return False

    cmd = [
        "zipalign",
        "-f",
        "-p",
        "4",
        str(input_path),
        str(output_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def merge_bundle(bundle_path: Path, output_path: Path) -> bool:
    """Merge split APK bundle into single APK using APKEditor.

    Args:
        bundle_path: Path to the XAPK/APKM bundle file.
        output_path: Path to the output merged APK file.

    Returns:
        True if merge succeeded, False otherwise.
    """
    if not isinstance(bundle_path, Path):
        raise ValueError("merge_bundle: bundle_path must be a Path object")
    if not _validate_path(bundle_path):
        raise ValueError(f"merge_bundle: path traversal detected in '{bundle_path}'")

    bundle_ext = bundle_path.suffix.lower()
    if bundle_ext not in (".xapk", ".apkm"):
        raise ValueError(f"merge_bundle: bundle must be .xapk or .apkm, got '{bundle_ext}'")

    if not _validate_path(output_path):
        raise ValueError(f"merge_bundle: path traversal detected in '{output_path}'")
    if output_path.suffix.lower() != ".apk":
        raise ValueError("merge_bundle: output must have .apk extension")

    if not bundle_path.exists():
        return False

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            cmd = [
                "java",
                "-jar",
                "APKEditor.jar",
                "merge",
                "-i",
                str(bundle_path),
                "-o",
                str(temp_path / "merged.apk"),
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            if result.returncode != 0:
                return False

            merged_apk = temp_path / "merged.apk"
            if not merged_apk.exists():
                return False

            shutil.copy2(merged_apk, output_path)
            return True

        except (subprocess.CalledProcessError, OSError):
            return False


def verify_signature(apk_path: Path) -> str | None:
    """Get APK signature SHA256 for verification.

    Args:
        apk_path: Path to the APK file to verify.

    Returns:
        SHA256 hash of the APK signature certificate, or None if verification fails.
    """
    _validate_apk_path(apk_path, "verify_signature")

    if not apk_path.exists():
        return None

    cmd = [
        "apksigner",
        "verify",
        "--print-certs",
        str(apk_path),
    ]
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
    """Detect the bundle type of a file.

    Args:
        file_path: Path to the file to detect.

    Returns:
        The detected BundleType.

    """
    if not file_path.exists():
        return BundleType.UNKNOWN

    suffix = file_path.suffix.lower()
    if suffix == ".apk":
        return BundleType.APK
    if suffix == ".xapk":
        return BundleType.XAPK
    if suffix == ".apkm":
        return BundleType.APKM

    # Try ZIP magic bytes
    try:
        with file_path.open("rb") as f:
            header = f.read(4)
        if header == b"PK\x03\x04":
            return BundleType.APK
    except OSError:
        pass

    return BundleType.UNKNOWN


class SplitAPKHandler:
    """Handler for split APK bundles (XAPK, APKM)."""

    def detect_bundle_type(self, file_path: Path) -> BundleType:
        """Detect the bundle type of a file.

        Args:
            file_path: Path to the file to detect.

        Returns:
            The detected BundleType.

        """
        return detect_bundle_type(file_path)

    def _find_apkeditor(self) -> Path | None:
        """Find APKEditor JAR in known locations.

        Returns:
            Path to APKEditor JAR if found, None otherwise.

        """
        candidates = [
            Path("bin/APKEditor.jar"),
            Path("APKEditor.jar"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def merge_splits(self, bundle_path: Path, output_path: Path) -> bool:
        """Merge a split APK bundle into a single APK.

        Args:
            bundle_path: Path to the bundle file.
            output_path: Path to write the merged APK.

        Returns:
            True if merge succeeded, False otherwise.

        """
        bundle_type = self.detect_bundle_type(bundle_path)
        if bundle_type == BundleType.APK:
            try:
                shutil.copy2(bundle_path, output_path)
                return True
            except OSError:
                return False
        if bundle_type in (BundleType.XAPK, BundleType.APKM):
            jar = self._find_apkeditor()
            if jar is None:
                return False
            try:
                result = subprocess.run(
                    ["java", "-jar", str(jar), "merge", "-i", str(bundle_path), "-o", str(output_path)],
                    capture_output=True,
                    check=False,
                )
                return result.returncode == 0
            except OSError:
                return False
        return False

    def extract_splits(self, bundle_path: Path, output_dir: Path) -> list[Path]:
        """Extract split APKs from a bundle.

        Args:
            bundle_path: Path to the bundle file.
            output_dir: Directory to extract splits into.

        Returns:
            List of extracted APK paths.

        """
        if not bundle_path.exists():
            return []

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            splits: list[Path] = []
            with zipfile.ZipFile(bundle_path, "r") as zf:
                for name in zf.namelist():
                    if name.endswith(".apk"):
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
        """Initialize AAPT2Manager.

        Args:
            cache_dir: Directory for caching downloaded AAPT2 binaries.

        """
        self.cache_dir = cache_dir or Path.home() / ".cache" / "revanced" / "aapt2"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_aapt2(self, arch: str = "arm64-v8a") -> Path | None:
        """Get the AAPT2 binary for the given architecture.

        Checks the cache first, then tries to download from known sources.
        Falls back to the system PATH.

        Args:
            arch: Target architecture (e.g., "arm64-v8a").

        Returns:
            Path to the AAPT2 binary, or None if unavailable.

        """
        from scripts.utils.network import gh_dl

        cached = self.cache_dir / f"aapt2-{arch}"
        if cached.exists():
            return cached

        for source in self.SOURCES:
            url = f"https://github.com/{source}/releases/latest/download/aapt2-{arch}"
            if gh_dl(cached, url):
                cached.chmod(0o755)
                return cached

        # Fallback to system PATH
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
        """Optimize an APK using AAPT2 resource filtering.

        Args:
            apk_path: Path to the input APK.
            output_path: Path to write the optimized APK.
            arch: Target architecture for AAPT2 binary.
            languages: Language codes to keep (e.g., ["en", "de"]).
            densities: Screen densities to keep (e.g., ["xxhdpi"]).

        Returns:
            True if optimization succeeded, False otherwise.

        """
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
            result = subprocess.run(cmd, capture_output=True, check=False)
            return result.returncode == 0
        except OSError:
            return False


def check_signature(apk_path: Path) -> bool:
    """Check if APK has valid v1+v2 signatures.

    Args:
        apk_path: Path to the APK file to check.

    Returns:
        True if APK has valid v1 and v2 signatures, False otherwise.
    """
    _validate_apk_path(apk_path, "check_signature")

    if not apk_path.exists():
        return False

    cmd = [
        "apksigner",
        "verify",
        "--v1-signing-enabled",
        "true",
        "--v2-signing-enabled",
        "true",
        "--v3-signing-enabled",
        "false",
        "--v4-signing-enabled",
        "false",
        str(apk_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False
