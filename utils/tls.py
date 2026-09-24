"""macOS TLS trust fix for outbound HTTPS (yfinance / curl_cffi / requests).

On some macOS setups an SSL-inspection root (corporate proxy, VPN, or
security software) is trusted by the system keychain but NOT by the CA
bundle that ``curl_cffi`` and ``requests`` use. System ``curl`` works, but
yfinance fails with::

    curl: (60) SSL certificate problem: self signed certificate in certificate chain

This module exports the keychain roots, merges them with ``certifi`` into a
combined bundle (cached under ~/.cache/alphafx), and points the standard CA
env vars at it. It is a no-op on non-macOS hosts (e.g. the Windows VM), so
it never interferes with MT5.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_KEYCHAINS = (
    "/Library/Keychains/System.keychain",
    "/System/Library/Keychains/SystemRootCertificates.keychain",
)


def ensure_macos_ca_bundle() -> None:
    """Ensure curl_cffi/requests trust the macOS system keychain roots."""
    if sys.platform != "darwin" or os.environ.get("ALPHAFX_CA_READY"):
        return
    try:
        import certifi
    except Exception:                                      # noqa: BLE001
        return

    cache_dir = Path.home() / ".cache" / "alphafx"
    bundle = cache_dir / "mac-ca-bundle.pem"
    try:
        if not bundle.exists() or bundle.stat().st_size == 0:
            cache_dir.mkdir(parents=True, exist_ok=True)
            parts = [Path(certifi.where()).read_text()]
            for kc in _KEYCHAINS:
                try:
                    res = subprocess.run(                  # noqa: S603
                        ["security", "find-certificate", "-a", "-p", kc],
                        capture_output=True, text=True, timeout=15,
                    )
                    if res.returncode == 0 and res.stdout:
                        parts.append(res.stdout)
                except Exception:                          # noqa: BLE001
                    pass
            bundle.write_text("\n".join(parts))

        os.environ.setdefault("CURL_CA_BUNDLE", str(bundle))
        os.environ.setdefault("SSL_CERT_FILE", str(bundle))
        os.environ.setdefault("REQUESTS_CA_BUNDLE", str(bundle))
        os.environ["ALPHAFX_CA_READY"] = "1"
    except Exception:                                      # noqa: BLE001
        pass
