#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import hashlib
from pathlib import Path


BASE_NAME = "brcmfmac4355c1-pcie"

SOURCES = {
    "rudderb.trx": (
        732185,
        "29276526471d794c59646b0ba89c31c2e5c48b88435412f22e3cfee32c8d441d",
    ),
    "rudderb.clmb": (
        9097,
        "bfe78741f0cb1e80aea37cd99727af2adef8e9357bfe02fa4d7a278f6a088d87",
    ),
    "rudderb.txcb": (
        602,
        "3fc2d256403ed4b429e160dc83990092402098a82003a0bc241282ce3cd7fcee",
    ),
    "P-rudderb_M-YSBU_V-m__m-2.5.txt": (
        5386,
        "23d0be41c025c935db90b95143c62ef2203e5e7543c20a1bfadefd56fd5b68a1",
    ),
    "P-rudderb_M-YSBU_V-u__m-4.3.txt": (
        5396,
        "26fa336993183f93f342a2294326b9be51cc57f95f65a70dc48a44daefa66a67",
    ),
}

COMMON_FILES = {
    "bin": "rudderb.trx",
    "clm_blob": "rudderb.clmb",
    "txcap_blob": "rudderb.txcb",
}

NVRAM_M = "P-rudderb_M-YSBU_V-m__m-2.5.txt"
NVRAM_U = "P-rudderb_M-YSBU_V-u__m-4.3.txt"

BOARDS = {
    "apple,rudderb": NVRAM_M,
    "apple,rudderb-XX": NVRAM_M,
    "apple,rudderb-YSBU-m-2.5": NVRAM_M,
    "apple,rudderb-YSBU-m-2.5-XX": NVRAM_M,
    "apple,rudderb-YSBU-u-4.3": NVRAM_U,
    "apple,rudderb-YSBU-u-4.3-XX": NVRAM_U,
}


def read_verified(source_dir, name):
    path = source_dir / name
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise SystemExit(f"missing source file: {path}") from None

    expected_size, expected_hash = SOURCES[name]
    actual_hash = hashlib.sha256(data).hexdigest()
    if len(data) != expected_size:
        raise SystemExit(
            f"unexpected size for {path}: expected {expected_size}, got {len(data)}"
        )
    if actual_hash != expected_hash:
        raise SystemExit(
            f"unexpected SHA-256 for {path}:\n"
            f"  expected {expected_hash}\n"
            f"  received {actual_hash}"
        )
    return data


def write_file(path, data):
    path.write_bytes(data)
    path.chmod(0o644)


def main():
    parser = argparse.ArgumentParser(
        description="Stage verified iPad7,12 BCM4355C1 firmware for brcmfmac"
    )
    parser.add_argument(
        "source",
        type=Path,
        help="22H355 C-4355__s-C1 directory extracted by ipsw",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="new output directory; a brcm/ tree is created below it",
    )
    args = parser.parse_args()

    source_dir = args.source.resolve()
    output_dir = args.output.resolve()
    if not source_dir.is_dir():
        raise SystemExit(f"source directory does not exist: {source_dir}")
    if output_dir.exists():
        raise SystemExit(f"output path already exists: {output_dir}")

    verified = {name: read_verified(source_dir, name) for name in SOURCES}
    brcm_dir = output_dir / "brcm"
    brcm_dir.mkdir(parents=True)

    for board, nvram in BOARDS.items():
        for extension, source_name in COMMON_FILES.items():
            destination = brcm_dir / f"{BASE_NAME}.{board}.{extension}"
            write_file(destination, verified[source_name])
        destination = brcm_dir / f"{BASE_NAME}.{board}.txt"
        write_file(destination, verified[nvram])

    generated = sorted(brcm_dir.iterdir())
    if len(generated) != 24 or any(not path.is_file() for path in generated):
        raise SystemExit("internal error: expected 24 regular firmware files")

    manifest = []
    for path in generated:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.append(f"{digest}  brcm/{path.name}\n")
    (output_dir / "SHA256SUMS").write_text("".join(manifest), encoding="ascii")

    print(f"Verified 5 Apple source files and wrote {len(generated)} files")
    print(f"Firmware tree: {brcm_dir}")
    print(f"Manifest:      {output_dir / 'SHA256SUMS'}")


if __name__ == "__main__":
    main()
