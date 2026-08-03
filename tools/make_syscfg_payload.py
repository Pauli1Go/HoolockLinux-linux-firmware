#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import os
import struct
from pathlib import Path


SYSCFG_HEADER = struct.Struct("<4sIIIII")
SYSCFG_KEY = struct.Struct("<4s16s")
SYSCFG_JUMBO = struct.Struct("<4sIII")
SYSCFG_MAGIC = b"gfCS"
SYSCFG_JUMBO_MAGIC = b"BTNC"
PAYLOAD_MAGIC = b"m1n1_syscfg"
MAX_SYSCFG_SIZE = 1024 * 1024

REQUIRED_KEYS = {
    "WMac": 6,
    "WCAL": 1,
    "BMac": 6,
    "LSCI": 8 + 0x54,
}


def decode_key(raw_name):
    try:
        return raw_name[::-1].decode("ascii")
    except UnicodeDecodeError:
        return None


def parse_syscfg(blob):
    if len(blob) < SYSCFG_HEADER.size:
        raise ValueError("SysCfg is too small for its header")
    if len(blob) > MAX_SYSCFG_SIZE:
        raise ValueError("SysCfg exceeds the m1n1 1 MiB limit")

    magic, _unk0, declared_size, _version, _unk1, key_count = (
        SYSCFG_HEADER.unpack_from(blob)
    )
    if magic != SYSCFG_MAGIC:
        raise ValueError("invalid SysCfg magic")
    if declared_size != len(blob):
        raise ValueError(
            f"declared SysCfg size {declared_size} does not match input size "
            f"{len(blob)}"
        )
    if key_count > (declared_size - SYSCFG_HEADER.size) // SYSCFG_KEY.size:
        raise ValueError("SysCfg key table exceeds the declared size")

    required = {}
    for index in range(key_count):
        entry_offset = SYSCFG_HEADER.size + index * SYSCFG_KEY.size
        raw_name, value = SYSCFG_KEY.unpack_from(blob, entry_offset)

        if raw_name == SYSCFG_JUMBO_MAGIC:
            jumbo_name, value_size, value_offset, _reserved = (
                SYSCFG_JUMBO.unpack(value)
            )
            name = decode_key(jumbo_name)
            if (
                value_offset > declared_size
                or value_size > declared_size - value_offset
            ):
                label = name if name is not None else "non-ASCII"
                raise ValueError(f"SysCfg jumbo key {label} exceeds the declared size")
            key_value = blob[value_offset : value_offset + value_size]
        else:
            name = decode_key(raw_name)
            key_value = value

        if name not in REQUIRED_KEYS:
            continue
        if name in required:
            raise ValueError(f"duplicate required SysCfg key {name}")
        required[name] = key_value

    missing = sorted(set(REQUIRED_KEYS) - set(required))
    if missing:
        raise ValueError(f"missing required D111 SysCfg keys: {', '.join(missing)}")

    for name, minimum_size in REQUIRED_KEYS.items():
        if len(required[name]) < minimum_size:
            raise ValueError(
                f"SysCfg key {name} is too short: expected at least "
                f"{minimum_size} bytes, got {len(required[name])}"
            )

    validate_lsci(required["LSCI"])
    return required


def validate_lsci(data):
    if len(data) % 2:
        raise ValueError("LSCI value has an odd byte length")
    if data[1] != 3 or data[2] != 1 or data[3] != 8:
        raise ValueError("unsupported LSCI calibration header")
    if struct.unpack_from("<H", data, 4)[0] != len(data):
        raise ValueError("LSCI header length does not match its SysCfg value")

    checksum = sum(
        struct.unpack_from("<H", data, offset)[0]
        for offset in range(0, len(data), 2)
    )
    if checksum & 0xFFFF != 0xFFFF:
        raise ValueError("invalid LSCI calibration checksum")

    record = data[8:]
    if record[0] != 0 or record[3] != 0x52 or record[4] != 1:
        raise ValueError("unsupported LSCI v3 calibration record")


def write_private_file(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        stream = os.fdopen(descriptor, "wb")
        descriptor = -1
        with stream:
            stream.write(data)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Validate a private D111 SysCfg image and create a bounded m1n1 "
            "payload component"
        )
    )
    parser.add_argument("input", type=Path, help="private 128 KiB D111 SysCfg image")
    parser.add_argument(
        "output",
        type=Path,
        help="new private m1n1 SysCfg payload component",
    )
    args = parser.parse_args()

    try:
        blob = args.input.read_bytes()
    except FileNotFoundError:
        raise SystemExit(f"input file does not exist: {args.input}") from None
    except OSError as error:
        raise SystemExit(f"failed to read input file: {error}") from None

    try:
        parse_syscfg(blob)
    except ValueError as error:
        raise SystemExit(f"invalid D111 SysCfg: {error}") from None

    payload = PAYLOAD_MAGIC + struct.pack("<I", len(blob)) + blob
    try:
        write_private_file(args.output, payload)
    except FileExistsError:
        raise SystemExit(f"refusing to overwrite output file: {args.output}") from None
    except OSError as error:
        raise SystemExit(f"failed to write output file: {error}") from None

    print("Validated the required D111 SysCfg records")
    print(f"Wrote private m1n1 component with mode 0600: {args.output}")


if __name__ == "__main__":
    main()
