# Reproducing iPad7/J172 Linux firmware

This repository documents how to reproduce the firmware required by
HoolockLinux on the cellular seventh-generation iPad (`iPad7,12`,
T8010/J172). It covers the Apple SmartIO and Z2 touchscreen firmware, the
Broadcom BCM4355C1 Wi-Fi files used by `brcmfmac`, the BCM4355C1 Bluetooth
Patchram firmware, and the private SysCfg data used by the supported drivers.

The completed installation contains:

```text
/lib/firmware/apple/t8010-smartio.bin
/lib/firmware/apple/dfrmtfw-j172-k1f19-6.bin
/lib/firmware/brcm/BCM4355C1.hcd
/lib/firmware/brcm/brcmfmac4355c1-pcie.apple,rudderb-*.bin
/lib/firmware/brcm/brcmfmac4355c1-pcie.apple,rudderb-*.txt
/lib/firmware/brcm/brcmfmac4355c1-pcie.apple,rudderb-*.clm_blob
/lib/firmware/brcm/brcmfmac4355c1-pcie.apple,rudderb-*.txcap_blob
```

This repository does not distribute Apple firmware, Wi-Fi NVRAM, or
device-specific calibration. The steps below extract the common firmware from
Apple's public iPadOS restore image and read private data only from the user's
own iPad.

The documented and validated reference image is iPadOS 18.7.9 (22H355) for
`iPad7,12`. Do not reuse build-specific offsets or hashes with a different
iPadOS release. Commands are run from the repository root unless a section
explicitly says to run them on the iPad.

## Requirements

- [`ipsw`](https://github.com/blacktop/ipsw), tested with version 3.1.696
- Python 3
- `curl`
- `shasum` on macOS or an equivalent SHA-256 tool
- Git, `make`, and a C compiler to build `makez2fw` and `hcdpack`
- Linux running on the target iPad to read its SysCfg partition
- root access to the target root filesystem or initramfs for installation
- BlueZ on the running Linux system for Bluetooth control and verification

Clone the repository and enter it:

```sh
git clone --depth 1 \
  https://github.com/Pauli1Go/HoolockLinux-linux-firmware.git
cd HoolockLinux-linux-firmware
```

If the repository is already checked out, continue from its root directory.

## 1. Download and verify the restore image

Download the exact tested IPSW directly from Apple's CDN:

[Download iPadOS 18.7.9 (22H355) for iPad7,12](https://updates.cdn-apple.com/2026WinterFCS/fullrestores/122-57592/FBDFE8FD-7949-4258-B392-F56D6CD4B8FA/iPad_10.2_18.7.9_22H355_Restore.ipsw)

Or download it from the terminal:

```sh
curl --fail --location --continue-at - \
  --output iPad_10.2_18.7.9_22H355_Restore.ipsw \
  'https://updates.cdn-apple.com/2026WinterFCS/fullrestores/122-57592/FBDFE8FD-7949-4258-B392-F56D6CD4B8FA/iPad_10.2_18.7.9_22H355_Restore.ipsw'
```

Verify the complete download before continuing:

```sh
test "$(wc -c < iPad_10.2_18.7.9_22H355_Restore.ipsw | tr -d ' ')" = 7891302055
shasum -a 256 iPad_10.2_18.7.9_22H355_Restore.ipsw
```

Expected SHA-256:

```text
972bf5cbb53c31d3ec5d3120ddd2e629fd1c08c8b34c4de00c535bc9fffcfceb
```

Stop if either the size or hash differs.

## 2. Extract the Apple SmartIO firmware

The SmartIO firmware is embedded in the
`com.apple.driver.AppleT8010SmartIO` kernel extension. It is the
`__DATA.__firmware` payload passed to `AppleSmartIOFirmware`; it is not the
J172 multitouch firmware extracted in the next section.

For the decompressed 22H355 `iPad7,12` kernelcache, the payload is located at:

```text
section:      __DATA.__firmware
file offset:  0x02a46000
size:         0x00088060 (557152 bytes)
```

Extract the kernelcache:

```sh
ipsw extract \
  --kernel \
  --device iPad7,12 \
  --output kernel \
  iPad_10.2_18.7.9_22H355_Restore.ipsw
```

Verify the decompressed kernelcache:

```sh
test "$(wc -c < 'kernel/22H355__iPad7,12/kernelcache.release.iPad7,11_12' | tr -d ' ')" = 48529408
shasum -a 256 'kernel/22H355__iPad7,12/kernelcache.release.iPad7,11_12'
```

Expected SHA-256:

```text
f0c322154b4927f230b0ed1d06ec445872d6b809c1a0d2acbef36e177c5379e3
```

Only continue if this hash matches. Extract the embedded section:

```sh
python3 - <<'PY'
from pathlib import Path

kernelcache = Path(
    "kernel/22H355__iPad7,12/kernelcache.release.iPad7,11_12"
)
output = Path("t8010-smartio.bin")
offset = 0x02A46000
size = 0x00088060

with kernelcache.open("rb") as stream:
    stream.seek(offset)
    firmware = stream.read(size)

if len(firmware) != size:
    raise SystemExit(
        f"short read: expected {size} bytes, received {len(firmware)}"
    )

output.write_bytes(firmware)
PY
```

Verify the result:

```sh
test "$(wc -c < t8010-smartio.bin | tr -d ' ')" = 557152
shasum -a 256 t8010-smartio.bin
```

Expected SHA-256:

```text
71d274a106f5912ed33552ba75ae76cc5081fc7063935ec938f9cb503df38199
```

## 3. Extract the J172 multitouch firmware

Extract the IM4P from the same IPSW:

```sh
ipsw extract \
  --flat \
  --pattern '.*J172_Multitouch\.im4p$' \
  --output touch \
  iPad_10.2_18.7.9_22H355_Restore.ipsw
```

`ipsw` places this file in a build/device-group subdirectory named
`22H355__iPad7,11_12`.

Verify the IM4P:

```sh
test "$(wc -c < 'touch/22H355__iPad7,11_12/J172_Multitouch.im4p' | tr -d ' ')" = 2205551
shasum -a 256 'touch/22H355__iPad7,11_12/J172_Multitouch.im4p'
```

Expected SHA-256:

```text
159f75dbbbf694a47af0fa16d00f2cbf3cf9a3dd34bfdb8da5db1d167a3e9889
```

Extract its payload:

```sh
ipsw img4 im4p extract \
  --output J172_Multitouch.mtfw \
  'touch/22H355__iPad7,11_12/J172_Multitouch.im4p'
```

Verify the MTFW:

```sh
test "$(wc -c < J172_Multitouch.mtfw | tr -d ' ')" = 2205526
shasum -a 256 J172_Multitouch.mtfw
```

Expected SHA-256:

```text
cb67cae5956af0ead9f4ffbc2a5e6f2ffdfea667db51e379d24fd3b6713ffbdf
```

## 4. Read the device-specific SysCfg

This section runs on the target iPad under Linux.

On the tested HoolockLinux storage layout, SysCfg is exposed as
`/dev/nvme0n3`. Confirm the block device and its exact size before reading it;
do not assume the same node is correct on a different storage layout.

```sh
test -b /dev/nvme0n3
test "$(blockdev --getsize64 /dev/nvme0n3)" = 131072

dd if=/dev/nvme0n3 \
  of=/tmp/syscfg.bin \
  bs=131072 \
  count=1 \
  status=progress

test "$(wc -c < /tmp/syscfg.bin | tr -d ' ')" = 131072
sha256sum /tmp/syscfg.bin
```

The `dd` command only reads from NVMe. It does not write to the partition.

Return to the development computer and copy the file into the repository
working directory:

```sh
IPAD_ADDRESS=172.16.42.1
scp "root@$IPAD_ADDRESS:/tmp/syscfg.bin" .
chmod 0600 syscfg.bin
test "$(wc -c < syscfg.bin | tr -d ' ')" = 131072
```

After confirming the copy, remove the temporary iPad-side file:

```sh
ssh "root@$IPAD_ADDRESS" rm -f /tmp/syscfg.bin
```

SysCfg contains device-specific touchscreen calibration, the Wi-Fi MAC
address in `WMac`, the Wi-Fi calibration blob in `WCAL`, the Bluetooth address
in `BMac`, and Bluetooth calibration records including `BTRx`, `BTTx`, and
`BCAL`. Do not reuse a dump from another iPad. Never publish it, attach it to a
bug report, or commit it to Git.

The patched loader supplies `BMac` as the standard Device Tree
`local-bd-address`. Bluetooth RF calibration from `BTRx`, `BTTx`, and `BCAL`
is still open and is not implemented in the Linux driver or loader path. The
controller therefore currently operates with the calibration contained in, or
defaults selected by, its Patchram firmware.

## 5. Build the calibrated Z2 firmware

The tested converter source is included in this repository. Build it with:

```sh
make -C makez2fw
```

Generate the Linux Z2 firmware container:

```sh
makez2fw/makez2fw \
  'K1F19,6' \
  J172_Multitouch.mtfw \
  syscfg.bin \
  dfrmtfw-j172-k1f19-6.bin
```

Verify that a container was produced:

```sh
test -s dfrmtfw-j172-k1f19-6.bin
```

The output contains calibration from `syscfg.bin`; its hash is therefore
expected to differ between devices. Treat the generated file as private.

## 6. Extract the BCM4355C1 Wi-Fi source files

The J172 Wi-Fi firmware is stored in the iPadOS filesystem under:

```text
System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/Firmware/C-4355__s-C1/
```

Extract only the five files needed by the tested J172 profiles:

```sh
ipsw extract \
  --files \
  --pattern '^System/Library/DriverExtensions/com\.apple\.DriverKit-AppleBCMWLAN\.dext/Firmware/C-4355__s-C1/(rudderb\.(trx|clmb|txcb)|P-rudderb_M-YSBU_V-(m__m-2\.5|u__m-4\.3)\.txt)$' \
  --output wifi \
  iPad_10.2_18.7.9_22H355_Restore.ipsw
```

Set the extracted source directory:

```sh
WIFI_SOURCE='wifi/22H355__iPad7,11_12/System/Library/DriverExtensions/com.apple.DriverKit-AppleBCMWLAN.dext/Firmware/C-4355__s-C1'
test -d "$WIFI_SOURCE"
```

The staging helper verifies every source before creating any output:

| Source file | Size | SHA-256 |
| --- | ---: | --- |
| `rudderb.trx` | 732185 | `29276526471d794c59646b0ba89c31c2e5c48b88435412f22e3cfee32c8d441d` |
| `rudderb.clmb` | 9097 | `bfe78741f0cb1e80aea37cd99727af2adef8e9357bfe02fa4d7a278f6a088d87` |
| `rudderb.txcb` | 602 | `3fc2d256403ed4b429e160dc83990092402098a82003a0bc241282ce3cd7fcee` |
| `P-rudderb_M-YSBU_V-m__m-2.5.txt` | 5386 | `23d0be41c025c935db90b95143c62ef2203e5e7543c20a1bfadefd56fd5b68a1` |
| `P-rudderb_M-YSBU_V-u__m-4.3.txt` | 5396 | `26fa336993183f93f342a2294326b9be51cc57f95f65a70dc48a44daefa66a67` |

Stop if extraction or verification reports a mismatch.

## 7. Stage the Wi-Fi firmware for brcmfmac

Apple and Linux use different suffixes for the same data:

| Apple source | brcmfmac suffix |
| --- | --- |
| `rudderb.trx` | `.bin` |
| `rudderb.clmb` | `.clm_blob` |
| `rudderb.txcb` | `.txcap_blob` |
| `P-rudderb_*.txt` | `.txt` |

Create the complete firmware tree:

```sh
python3 tools/makebrcmfw.py "$WIFI_SOURCE" generated-wifi
```

Verify the generated manifest:

```sh
(cd generated-wifi && shasum -a 256 -c SHA256SUMS)
test "$(find generated-wifi/brcm -maxdepth 1 -type f | wc -l | tr -d ' ')" = 24
```

The helper writes six board-name groups with `.bin`, `.txt`, `.clm_blob`,
and `.txcap_blob` files:

```text
apple,rudderb
apple,rudderb-XX
apple,rudderb-YSBU-m-2.5
apple,rudderb-YSBU-m-2.5-XX
apple,rudderb-YSBU-u-4.3
apple,rudderb-YSBU-u-4.3-XX
```

The tested iPad selects `apple,rudderb-YSBU-m-2.5-XX`. Both known OTP
profiles are staged so `brcmfmac` can select the matching NVRAM without a
manual firmware override. The plain fallback uses the validated `m-2.5`
profile and is not a substitute for checking the OTP-specific request on a
different device.

## 8. Extract the BCM4355C1 Bluetooth firmware

The BCM4355C1 Bluetooth Patchram image is embedded in `/usr/sbin/BlueTool` in
the same iPadOS filesystem. Extract that file:

```sh
ipsw extract \
  --files \
  --pattern '^usr/sbin/BlueTool$' \
  --output bluetooth \
  iPad_10.2_18.7.9_22H355_Restore.ipsw

BLUETOOL='bluetooth/22H355__iPad7,11_12/usr/sbin/BlueTool'
test -f "$BLUETOOL"
```

Verify the extracted binary:

```sh
test "$(wc -c < "$BLUETOOL" | tr -d ' ')" = 5221024
shasum -a 256 "$BLUETOOL"
```

Expected SHA-256:

```text
dadd9b2086cbc98bb498e4899ce42303a3a03fe0509955bf2de583447532b0e0
```

Build the `hcdpack` extractor from the pinned Project Sandcastle revision:

```sh
git clone https://github.com/corellium/projectsandcastle.git
git -C projectsandcastle checkout \
  03db9c6ae04141eb940f3b9f56d446f50d57fadf
make -C projectsandcastle/hcdpack \
  CFLAGS='-O2 -Wall -I. -D_DARWIN_C_SOURCE'
```

The extra feature macro keeps `strdup()` visible when building this revision
with Apple's current Clang and is harmless on Linux.

Extract the Murata RudderB image selected by the validated J172 OTP profile:

```sh
projectsandcastle/hcdpack/hcdpack \
  "$BLUETOOL" \
  'C-4355__s-C1' \
  rudderB \
  'M-YSBU_V-m__m-2.5' \
  BCM4355C1.hcd
```

Verify the generated firmware:

```sh
test "$(wc -c < BCM4355C1.hcd | tr -d ' ')" = 76184
shasum -a 256 BCM4355C1.hcd
```

Expected SHA-256:

```text
27b778a87f086d8c23f0ad06c77e4b62de9af83182f100ddf4a6e59b1d4249b7
```

The profile above is tied to the tested Murata module. Do not silently reuse
it on a device whose Wi-Fi OTP reports a different module or NVRAM profile.
The generated HCD is the common Patchram image for that module profile; it
does not contain this iPad's private `BTRx`, `BTTx`, or `BCAL` RF calibration.

## 9. Install the firmware

Install the touch, Wi-Fi, and Bluetooth files into the target root filesystem:

```sh
sudo install -d /lib/firmware/apple /lib/firmware/brcm
sudo install -m 0644 t8010-smartio.bin \
  /lib/firmware/apple/t8010-smartio.bin
sudo install -m 0644 dfrmtfw-j172-k1f19-6.bin \
  /lib/firmware/apple/dfrmtfw-j172-k1f19-6.bin
sudo install -m 0644 BCM4355C1.hcd \
  /lib/firmware/brcm/BCM4355C1.hcd
sudo install -m 0644 generated-wifi/brcm/* /lib/firmware/brcm/
```

Install the normal Linux regulatory database and Bluetooth userspace from the
distribution. On Debian or Ubuntu:

```sh
sudo apt-get update
sudo apt-get install wireless-regdb bluez
sudo systemctl enable --now bluetooth.service
```

The tested kernel has the touch, Wi-Fi, and Bluetooth drivers built in, so all
firmware and `regulatory.db` must also be present in the early initramfs.
Generic initramfs dependency discovery may omit firmware for built-in drivers.
On Debian or Ubuntu, install the provided `initramfs-tools` hook and rebuild
the initramfs:

```sh
sudo install -m 0755 \
  initramfs-tools/hooks/hoolock-ipad7-firmware \
  /etc/initramfs-tools/hooks/hoolock-ipad7-firmware
sudo update-initramfs -u
```

For a manually assembled initramfs, copy the same paths below
`/lib/firmware` and preserve their names exactly.

Verify the installed files:

```sh
test -s /lib/firmware/apple/t8010-smartio.bin
test -s /lib/firmware/apple/dfrmtfw-j172-k1f19-6.bin
test -s /lib/firmware/brcm/BCM4355C1.hcd
test -s /lib/firmware/regulatory.db
test -s /lib/firmware/regulatory.db.p7s
test "$(find /lib/firmware/brcm -maxdepth 1 \
  -name 'brcmfmac4355c1-pcie.apple,rudderb*' \
  -type f | wc -l | tr -d ' ')" = 24
```

On Debian or Ubuntu, inspect the rebuilt initramfs as well:

```sh
INITRAMFS="/boot/initrd.img-$(uname -r)"
test -f "$INITRAMFS"
lsinitramfs "$INITRAMFS" | grep -q 'apple/t8010-smartio.bin$'
lsinitramfs "$INITRAMFS" | grep -q 'apple/dfrmtfw-j172-k1f19-6.bin$'
lsinitramfs "$INITRAMFS" | grep -q 'brcm/BCM4355C1.hcd$'
lsinitramfs "$INITRAMFS" | grep -q 'regulatory.db$'
lsinitramfs "$INITRAMFS" | grep -q 'regulatory.db.p7s$'
test "$(lsinitramfs "$INITRAMFS" |
  grep -c 'brcmfmac4355c1-pcie.apple,rudderb')" = 24
```

The kernel loads the Apple and Broadcom files automatically through the
standard Linux firmware API. No module parameter, firmware-path override,
driver rebind, or userspace firmware daemon is required.

## 10. Provide SysCfg to the patched m1n1 loader

Broadcom firmware files and SysCfg use different kernel interfaces. The
Wi-Fi and Bluetooth files above are loaded from `/lib/firmware`; the private
`WMac` and `WCAL` values are provided through NVMEM by the patched
[`m1n1-ipad7`](https://github.com/Pauli1Go/m1n1-ipad7) loader.

Create the bounded SysCfg payload component:

```sh
python3 - <<'PY'
from pathlib import Path
import struct

source = Path("syscfg.bin")
output = Path("m1n1-syscfg.payload")
blob = source.read_bytes()

if len(blob) != 131072:
    raise SystemExit(f"expected a 131072-byte SysCfg, received {len(blob)}")

output.write_bytes(b"m1n1_syscfg" + struct.pack("<I", len(blob)) + blob)
output.chmod(0o600)
PY

test "$(wc -c < m1n1-syscfg.payload | tr -d ' ')" = 131087
```

Append this component exactly once after the normal kernel, Device Tree, and
initramfs components when constructing a payload for the patched loader. The
loader reserves a private copy, publishes it as `apple,syscfg-rmem`, connects
the `WMac` and `WCAL` cells to the BCM4355 Wi-Fi device, and supplies the
Bluetooth `local-bd-address`. Do not install `syscfg.bin` under
`/lib/firmware`, and do not use a SysCfg dump from another iPad.

This does not provide Bluetooth RF calibration. Consumption of the private
`BTRx`, `BTTx`, and `BCAL` records remains unimplemented.

Both `syscfg.bin` and `m1n1-syscfg.payload` are ignored by this repository.
Keep them private and delete unneeded copies after the boot payload has been
built.

## 11. Verify the running system

After booting the patched kernel and m1n1 payload, verify automatic firmware
loading:

```sh
dmesg | grep -E 'apple-z2|brcmfmac|Firmware: BCM4355|TxCap blob|Bluetooth: hci0'
ip link show wlp2s0
rfkill list
test -e /sys/class/bluetooth/hci0
systemctl --no-pager --full status bluetooth.service
bluetoothctl show
```

On the validated J172, `brcmfmac` reports BCM4355/12 firmware
`9.30.516.0.3.50.104`, loads TxCap and the platform calibration blob, and
registers `wlp2s0`. NetworkManager, `nmcli`, `wpa_supplicant`, and `hostapd`
then use the ordinary Linux networking interfaces.

Station mode, WPA2, DHCP, Internet access, disconnect/reconnect, and hostapd
AP mode have been validated. The optional cfg80211 P2P-device interface is
not supported by the tested firmware; this does not affect station or AP
mode.

The J172 Bluetooth controller is exposed as a normal BlueZ HCI controller.
The kernel powers it through the standard serdev path, switches the Broadcom
controller and host UART to their runtime rates, and loads
`brcm/BCM4355C1.hcd` automatically with `request_firmware()`. Discovery,
pairing, reconnect, and A2DP audio have been validated through standard Linux
userspace. `bluetoothctl` can therefore control it after a normal boot without
a board-specific userspace loader or manual UART attachment.

Bluetooth calibration is not yet implemented. Until `BTRx`, `BTTx`, and
`BCAL` are supported, range, transmit power, receive sensitivity, and RF
performance must not be treated as fully calibrated or production-ready.
