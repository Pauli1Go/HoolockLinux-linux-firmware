#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only

import os
import struct
import tempfile
import unittest
from pathlib import Path

from tools import make_syscfg_payload as target


def reverse_name(name):
    return name.encode("ascii")[::-1]


def make_lsci():
    value = bytearray(8 + 0x54)
    value[1] = 3
    value[2] = 1
    value[3] = 8
    struct.pack_into("<H", value, 4, len(value))
    value[8] = 0
    value[11] = 0x52
    value[12] = 1
    checksum = sum(
        struct.unpack_from("<H", value, offset)[0]
        for offset in range(0, len(value), 2)
    )
    struct.pack_into("<H", value, len(value) - 2, (0xFFFF - checksum) & 0xFFFF)
    return bytes(value)


def make_syscfg(*, include_lsci=True, bad_jumbo=False):
    inline = {
        "WMac": b"\x02\x00\x00\x00\x00\x01" + bytes(10),
        "BMac": b"\x02\x00\x00\x00\x00\x02" + bytes(10),
    }
    jumbo = {"WCAL": b"calibration"}
    if include_lsci:
        jumbo["LSCI"] = make_lsci()

    entries = []
    for name, value in inline.items():
        entries.append(target.SYSCFG_KEY.pack(reverse_name(name), value))

    data_offset = target.SYSCFG_HEADER.size + (
        len(inline) + len(jumbo)
    ) * target.SYSCFG_KEY.size
    values = bytearray()
    for name, value in jumbo.items():
        offset = data_offset + len(values)
        if bad_jumbo and name == "WCAL":
            offset += 0x100000
        descriptor = target.SYSCFG_JUMBO.pack(
            reverse_name(name), len(value), offset, 0xFFFFFFFF
        )
        entries.append(target.SYSCFG_KEY.pack(target.SYSCFG_JUMBO_MAGIC, descriptor))
        values.extend(value)

    size = data_offset + len(values)
    header = target.SYSCFG_HEADER.pack(
        target.SYSCFG_MAGIC, 0x7C, size, 1, 0, len(entries)
    )
    return header + b"".join(entries) + values


class SysCfgPayloadTests(unittest.TestCase):
    def test_valid_syscfg_and_payload(self):
        blob = make_syscfg()
        required = target.parse_syscfg(blob)
        self.assertEqual(set(required), set(target.REQUIRED_KEYS))

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "m1n1-syscfg.payload"
            payload = target.PAYLOAD_MAGIC + struct.pack("<I", len(blob)) + blob
            target.write_private_file(output, payload)
            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_missing_lsci_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "LSCI"):
            target.parse_syscfg(make_syscfg(include_lsci=False))

    def test_bad_magic_is_rejected(self):
        blob = bytearray(make_syscfg())
        blob[:4] = b"bad!"
        with self.assertRaisesRegex(ValueError, "magic"):
            target.parse_syscfg(bytes(blob))

    def test_bad_declared_size_is_rejected(self):
        blob = bytearray(make_syscfg())
        struct.pack_into("<I", blob, 8, len(blob) + 1)
        with self.assertRaisesRegex(ValueError, "declared SysCfg size"):
            target.parse_syscfg(bytes(blob))

    def test_duplicate_required_key_is_rejected(self):
        blob = bytearray(make_syscfg())
        second_key_offset = target.SYSCFG_HEADER.size + target.SYSCFG_KEY.size
        blob[second_key_offset : second_key_offset + 4] = reverse_name("WMac")
        with self.assertRaisesRegex(ValueError, "duplicate.*WMac"):
            target.parse_syscfg(bytes(blob))

    def test_out_of_bounds_jumbo_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exceeds"):
            target.parse_syscfg(make_syscfg(bad_jumbo=True))

    def test_bad_lsci_checksum_is_rejected(self):
        blob = bytearray(make_syscfg())
        blob[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "checksum"):
            target.parse_syscfg(bytes(blob))

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing"
            output.write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                target.write_private_file(output, b"replacement")
            self.assertEqual(output.read_bytes(), b"keep")

    def test_output_mode_is_independent_of_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "private"
            previous_umask = os.umask(0o777)
            try:
                target.write_private_file(output, b"private")
            finally:
                os.umask(previous_umask)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
