# Reproducing iPhone 7 Plus/D111 Linux firmware

Before continuing, connect the iPhone in normal iOS mode, trust the computer,
and identify the hardware variant with `ideviceinfo` from
[`libimobiledevice`](https://libimobiledevice.org/):

```sh
ideviceinfo -k HardwareModel
ideviceinfo -k ProductType
```

- `D11AP` and `iPhone9,2`: stop here and use the
  [iPhone 7 Plus/D11 guide](iphone7-d11.md).
- `D111AP` and `iPhone9,4`: continue with this D111 guide.
- Any other value or a disagreement between both values: stop and identify
  the device before extracting or installing firmware.

This document describes how to reproduce the Apple firmware used by
HoolockLinux on the iPhone 7 Plus (`iPhone9,4`, T8010/D111). The documented
combination has been booted on hardware. The touchscreen has been verified
with physical touch input, and BCM4355 station-mode Wi-Fi has been verified
with a real WPA2 connection and data transfer. The BCM4355C0 Bluetooth
controller has been verified with automatic Patchram loading, its
device-specific address, discovery, connection, and A2DP audio.

The completed installation contains:

```text
/lib/firmware/apple/t8010-smartio.bin
/lib/firmware/apple/dfrmtfw-d111-c1f5e-2.bin
/lib/firmware/brcm/BCM.apple,d111.hcd
/lib/firmware/brcm/brcmfmac4355-pcie.apple,olaf.bin
/lib/firmware/brcm/brcmfmac4355-pcie.apple,olaf.clm_blob
/lib/firmware/brcm/brcmfmac4355-pcie.apple,olaf.txcap_blob
/lib/firmware/brcm/brcmfmac4355-pcie.apple,olaf-PRNL-*.txt
```

This repository does not distribute Apple firmware, Wi-Fi NVRAM, or
device-specific calibration. The commands below reproduce the common firmware
from one Apple restore image. The generated D111 touch container does not
contain device-specific calibration: the supported m1n1 loader copies touch
calibration from Apple's live Device Tree at every boot. Wi-Fi calibration and
CT821 ambient-light calibration are provided separately from the same
iPhone's private SysCfg. The Bluetooth device address comes from `BMac` in
that same private SysCfg; the common HCD file does not contain it.

The D111 Device Tree sets `brcm,board-type` to `apple,olaf`, matching Apple's
Wi-Fi module-instance name. All BCM4355 Wi-Fi files below therefore use
`apple,olaf`-qualified names so they can coexist with the D11 `sven` family.

This guide is specific to the iPhone 7 Plus D111. The smaller iPhone 7 uses
D10 and a different multitouch profile; D10 has not been validated by the
current HoolockLinux port and must not be treated as covered by these steps.
Other iPhone audio firmware remains outside the scope of the currently
validated port. Wi-Fi access-point mode is also not supported: a hotspot
reactivation caused a full system freeze during bring-up. The validated Wi-Fi
scope is station mode only.

Commands are run from the repository root unless stated otherwise.

## Requirements

- [`ipsw`](https://github.com/blacktop/ipsw), tested with version 3.1.696
- Python 3
- `curl`
- `shasum` on macOS or an equivalent SHA-256 tool
- Git, `make`, and a C compiler to build `makez2fw` and `hcdpack`
- a D111-capable HoolockLinux kernel and m1n1 loader
- root access to the target root filesystem or initramfs
- `initramfs-tools` when using the Debian installation method below
- BlueZ on the running Linux system for Bluetooth control and verification

Clone the repository and enter it:

```sh
git clone --depth 1 \
  https://github.com/Pauli1Go/HoolockLinux-linux-firmware.git
cd HoolockLinux-linux-firmware
```

## 1. Download and verify the D111 restore image

The validated D11 multitouch source comes from iOS 15.8.4 (19H390) for the
iPhone 7 Plus. Download that exact IPSW from Apple's CDN:

[Download iOS 15.8.4 (19H390) for iPhone9,4](https://updates.cdn-apple.com/2025WinterSeed/fullrestores/062-48481/770AB33F-5F75-44C0-9E23-65E8648D76C6/iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw)

Or download it from the terminal:

```sh
curl --fail --location --continue-at - \
  --output iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw \
  'https://updates.cdn-apple.com/2025WinterSeed/fullrestores/062-48481/770AB33F-5F75-44C0-9E23-65E8648D76C6/iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw'
```

Verify the complete file before mounting or extracting its filesystem:

```sh
test "$(wc -c < iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw | tr -d ' ')" = 5563988045
shasum -a 256 iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw
```

Expected SHA-256:

```text
bcb69450536a3909f3b6a49f278dfe634e8bfa9dc825f6ab5d1116fa569e657d
```

Stop if either value differs. Offsets, paths, and hashes in this guide are
not asserted for another iOS build.

## 2. Extract the native T8010 SmartIO firmware

SmartIO firmware is embedded in the Apple T8010 kernel extension. Extract the
iPhone 7 Plus kernelcache from the same IPSW downloaded above:

```sh
ipsw extract \
  --kernel \
  --device iPhone9,4 \
  --output smartio-kernel \
  iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw
```

Verify the decompressed kernelcache before using the pinned offset:

```sh
test "$(wc -c < 'smartio-kernel/19H390__iPhone9,4/kernelcache.release.iPhone9,2_4' | tr -d ' ')" = 44924928
shasum -a 256 \
  'smartio-kernel/19H390__iPhone9,4/kernelcache.release.iPhone9,2_4'
```

Expected SHA-256:

```text
3588eeca5ec84024fa11aeef1dc5a2f2e3d092fb82eff3a9d3e5a80f2606ec1d
```

Stop if the size or hash differs. For this exact kernelcache, the
`AppleT8010SmartIO` firmware begins at file offset `0x02705000` and is
`0x00088060` bytes long. Extract it with Python 3:

```sh
python3 - <<'PY'
from pathlib import Path

source = Path(
    "smartio-kernel/19H390__iPhone9,4/"
    "kernelcache.release.iPhone9,2_4"
)
output = Path("t8010-smartio.bin")
offset = 0x02705000
size = 0x00088060

with source.open("rb") as stream:
    stream.seek(offset)
    firmware = stream.read(size)

if len(firmware) != size:
    raise SystemExit(
        f"short read: expected {size} bytes, received {len(firmware)}"
    )

output.write_bytes(firmware)
PY

test "$(wc -c < t8010-smartio.bin | tr -d ' ')" = 557152
shasum -a 256 t8010-smartio.bin
```

Expected SHA-256:

```text
408adbb05e75469cbd9c4d94624fd116ae58be5f87cf40b5e495242a83140bcb
```

This native iOS 15.8.4 SmartIO image has been verified on the iPhone 7 Plus:
Linux booted from internal NVMe, systemd and the graphical target remained
active, and no SmartIO-related kernel error was reported.

## 3. Extract the D11 multitouch source

`D11.mtprops` is stored in the iOS filesystem, not as a top-level IPSW
component. Extract only that file:

```sh
ipsw extract \
  --files \
  --flat \
  --pattern '(^|/)usr/share/firmware/multitouch/D11\.mtprops$' \
  --output touch \
  iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw

test "$(find touch -type f -name D11.mtprops | wc -l | tr -d ' ')" = 1
test -f 'touch/19H390__iPhone9,2_4/D11.mtprops'
```

Verify the extracted property list:

```sh
test "$(wc -c < 'touch/19H390__iPhone9,2_4/D11.mtprops' | tr -d ' ')" = 116503
shasum -a 256 'touch/19H390__iPhone9,2_4/D11.mtprops'
```

Expected SHA-256:

```text
7f9b16b749dd0f3e12633ce5140220ea89317006dc0278b24cf2d815578e3ff6
```

The required D111 personality is `C1F5E,2`. Confirm that it is present:

```sh
grep -q '<key>C1F5E,2</key>' \
  'touch/19H390__iPhone9,2_4/D11.mtprops'
```

## 4. Build the D111 Z2 firmware container

Build the converter included in this repository:

```sh
make -C makez2fw
```

Generate a container with typed dynamic-calibration requests:

```sh
makez2fw/makez2fw \
  --dynamic-calibration \
  'C1F5E,2' \
  'touch/19H390__iPhone9,2_4/D11.mtprops' \
  dfrmtfw-d111-c1f5e-2.bin
```

This command deliberately has no `syscfg.bin` argument. Do not append one and
do not reuse the calibrated iPad command line. Verify the deterministic
output:

```sh
test "$(wc -c < dfrmtfw-d111-c1f5e-2.bin | tr -d ' ')" = 76724
shasum -a 256 dfrmtfw-d111-c1f5e-2.bin
```

Expected SHA-256:

```text
57f094f2afbc21c3eca511f5b5d0a90e276789a0a5e8f770528e682fdfa660d6
```

The converter should report one configuration and four calibration requests:

| Provider | Apple Device Tree property | Address | Maximum size |
| ---: | --- | ---: | ---: |
| 0 | `multi-touch-calibration` | `0x10009000` | `0x708` |
| 1 | `orb-gap-cal` | `0x00400568` | `0x3e0` |
| 2 | `orb-force-cal` | `0x004010d0` | `0x5c4` |
| 3 | `shape-dynamic-accel-cal` | `0x00401a10` | `0x0d0` |

The source and both generated files are derived from Apple firmware. Do not
commit or redistribute them.

## 5. Extract the D111 BCM4355 Wi-Fi source files

The D111 Apple Device Tree identifies the Wi-Fi chipset as `4355` and its
module instance as `olaf`. The matching files are stored in the same iOS
15.8.4 filesystem under:

```text
usr/share/firmware/wifi/C-4355__s-C0/
```

Extract only the seven files needed by the available D111 PRNL profiles from
the same IPSW already downloaded in section 1:

```sh
ipsw extract \
  --files \
  --pattern '(^|/)usr/share/firmware/wifi/C-4355__s-C0/(olaf\.(trx|clmb|txcb)|P-olaf_M-PRNL_V-(m__m-(5\.3|5\.7)|u__m-(5\.3|5\.9))\.txt)$' \
  --output wifi \
  iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw
```

Set and verify the extracted source directory:

```sh
WIFI_SOURCE='wifi/19H390__iPhone9,2_4/usr/share/firmware/wifi/C-4355__s-C0'
test -d "$WIFI_SOURCE"
test "$(find "$WIFI_SOURCE" -maxdepth 1 -type f | wc -l | tr -d ' ')" = 7
```

Verify every source before renaming or installing it:

| Source file | Size | SHA-256 |
| --- | ---: | --- |
| `olaf.trx` | 746961 | `420531da4f43040bdc851e2043e73ac657db0883406e607afcaef7cfbbfc82ba` |
| `olaf.clmb` | 9248 | `fa99d9332574a11d8ff8c675474b47f1af7c3e7333e7acb9450dca11ab52c4d4` |
| `olaf.txcb` | 632 | `1b06fbc502499af122d03a7daff97c03384d49feb0fa2717f0b62f3d2d213345` |
| `P-olaf_M-PRNL_V-m__m-5.3.txt` | 5170 | `a4dd05f5a6bb76018ac3d595b7193451cbdc1ab291ff46dc70a09e989ea31251` |
| `P-olaf_M-PRNL_V-m__m-5.7.txt` | 5170 | `a4dd05f5a6bb76018ac3d595b7193451cbdc1ab291ff46dc70a09e989ea31251` |
| `P-olaf_M-PRNL_V-u__m-5.3.txt` | 5168 | `85acf1e7dfb15c65daf329105860aac7b05c955933eb0291c37d4ce1859c8dd0` |
| `P-olaf_M-PRNL_V-u__m-5.9.txt` | 5168 | `85acf1e7dfb15c65daf329105860aac7b05c955933eb0291c37d4ce1859c8dd0` |

These seven files match byte-for-byte the copies used during the successful
station-mode hardware test. A second IPSW is therefore neither needed nor
used by this guide.

## 6. Stage the Wi-Fi firmware for brcmfmac

Apple and Linux use different names for the same data:

| Apple source | brcmfmac destination |
| --- | --- |
| `olaf.trx` | `brcmfmac4355-pcie.apple,olaf.bin` |
| `olaf.clmb` | `brcmfmac4355-pcie.apple,olaf.clm_blob` |
| `olaf.txcb` | `brcmfmac4355-pcie.apple,olaf.txcap_blob` |
| `P-olaf_M-PRNL_V-m__m-5.3.txt` | `brcmfmac4355-pcie.apple,olaf-PRNL-m-5.3.txt` |
| `P-olaf_M-PRNL_V-m__m-5.7.txt` | `brcmfmac4355-pcie.apple,olaf-PRNL-m-5.7.txt` |
| `P-olaf_M-PRNL_V-u__m-5.3.txt` | `brcmfmac4355-pcie.apple,olaf-PRNL-u-5.3.txt` |
| `P-olaf_M-PRNL_V-u__m-5.9.txt` | `brcmfmac4355-pcie.apple,olaf-PRNL-u-5.9.txt` |

Create a new staging tree with the exact names requested by modern
`brcmfmac` for board type `apple,olaf`:

```sh
test ! -e generated-wifi
install -d generated-wifi/brcm
install -m 0644 "$WIFI_SOURCE/olaf.trx" \
  generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf.bin
install -m 0644 "$WIFI_SOURCE/olaf.clmb" \
  generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf.clm_blob
install -m 0644 "$WIFI_SOURCE/olaf.txcb" \
  generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf.txcap_blob
install -m 0644 "$WIFI_SOURCE/P-olaf_M-PRNL_V-m__m-5.3.txt" \
  generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf-PRNL-m-5.3.txt
install -m 0644 "$WIFI_SOURCE/P-olaf_M-PRNL_V-m__m-5.7.txt" \
  generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf-PRNL-m-5.7.txt
install -m 0644 "$WIFI_SOURCE/P-olaf_M-PRNL_V-u__m-5.3.txt" \
  generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf-PRNL-u-5.3.txt
install -m 0644 "$WIFI_SOURCE/P-olaf_M-PRNL_V-u__m-5.9.txt" \
  generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf-PRNL-u-5.9.txt
```

Verify that the tree contains exactly seven files and that staging did not
change their bytes:

```sh
test "$(find generated-wifi/brcm -maxdepth 1 -type f | wc -l | tr -d ' ')" = 7
test "$(shasum -a 256 generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf.bin | awk '{print $1}')" = \
  420531da4f43040bdc851e2043e73ac657db0883406e607afcaef7cfbbfc82ba
test "$(shasum -a 256 generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf.clm_blob | awk '{print $1}')" = \
  fa99d9332574a11d8ff8c675474b47f1af7c3e7333e7acb9450dca11ab52c4d4
test "$(shasum -a 256 generated-wifi/brcm/brcmfmac4355-pcie.apple,olaf.txcap_blob | awk '{print $1}')" = \
  1b06fbc502499af122d03a7daff97c03384d49feb0fa2717f0b62f3d2d213345
for firmware in generated-wifi/brcm/*-PRNL-m-*.txt; do
  test "$(shasum -a 256 "$firmware" | awk '{print $1}')" = \
    a4dd05f5a6bb76018ac3d595b7193451cbdc1ab291ff46dc70a09e989ea31251
done
for firmware in generated-wifi/brcm/*-PRNL-u-*.txt; do
  test "$(shasum -a 256 "$firmware" | awk '{print $1}')" = \
    85acf1e7dfb15c65daf329105860aac7b05c955933eb0291c37d4ce1859c8dd0
done
```

The `m-5.3`/`m-5.7` pair and the `u-5.3`/`u-5.9` pair currently contain
identical bytes, but all four names must remain available because the
firmware-request name includes the detected PRNL profile. Do not substitute
the iPad 7 `rudderb` firmware or a different Apple module-instance name.

## 7. Extract the BCM4355C0 Bluetooth firmware

The BCM4355C0 Bluetooth Patchram image is embedded in `/usr/sbin/BlueTool` in
the same iOS filesystem. Extract that file from the IPSW already verified in
section 1:

```sh
ipsw extract \
  --files \
  --pattern '^usr/sbin/BlueTool$' \
  --output bluetooth \
  iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw

BLUETOOL='bluetooth/19H390__iPhone9,2_4/usr/sbin/BlueTool'
test -f "$BLUETOOL"
```

Verify the extracted binary:

```sh
test "$(wc -c < "$BLUETOOL" | tr -d ' ')" = 9710640
shasum -a 256 "$BLUETOOL"
```

Expected SHA-256:

```text
78115abe9705d30596768231d2f1587bf68670f6a7a2d1db7d88620aa54cca8d
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

The validated iPhone reports BCM4355 revision C0 with the Olaf PRNL `m-5.7`
Murata profile. Extract exactly that Patchram image using the OTP strings:

```sh
projectsandcastle/hcdpack/hcdpack \
  "$BLUETOOL" \
  'C-4355__s-C0' \
  olaf \
  'M-PRNL_V-m__m-5.7' \
  BCM.apple,d111.hcd
```

Verify the generated firmware:

```sh
test "$(wc -c < BCM.apple,d111.hcd | tr -d ' ')" = 91023
shasum -a 256 BCM.apple,d111.hcd
```

Expected SHA-256:

```text
4b5174cdfce25ae2e407a9f934866546ce204a202925074b32c5dc7cf96db714
```

The profile is tied to the validated Murata module. Do not silently reuse it
on a D111 whose Wi-Fi OTP identifies the USI variant or another NVRAM profile.
The generated HCD is the common Patchram image and contains neither this
iPhone's private `BMac` address nor its `BTRx`, `BTTx`, or `BCAL` RF records.

## 8. Install the firmware

Install the common Apple and Broadcom files into the target root filesystem
using the exact names requested by the Device Tree and drivers:

```sh
sudo install -d /lib/firmware/apple /lib/firmware/brcm
sudo install -m 0644 t8010-smartio.bin \
  /lib/firmware/apple/t8010-smartio.bin
sudo install -m 0644 dfrmtfw-d111-c1f5e-2.bin \
  /lib/firmware/apple/dfrmtfw-d111-c1f5e-2.bin
sudo install -m 0644 BCM.apple,d111.hcd \
  /lib/firmware/brcm/BCM.apple,d111.hcd
sudo install -m 0644 generated-wifi/brcm/* /lib/firmware/brcm/
```

Install the normal Linux regulatory database and Bluetooth userspace as well.
On Debian:

```sh
sudo apt-get update
sudo apt-get install wireless-regdb bluez
sudo systemctl enable --now bluetooth.service
```

The validated kernel builds the Apple Z2, SmartIO, brcmfmac, and Bluetooth
UART drivers into the kernel, so all firmware and the regulatory database
must be present in the early initramfs. In particular, the Bluetooth UART
probes before `switch_root`; finding the HCD only in the root filesystem is
too late. Generic dependency detection can omit firmware for built-in
drivers. On Debian, install the provided `initramfs-tools` hook and rebuild
the initramfs:

```sh
sudo install -m 0755 \
  initramfs-tools/hooks/hoolock-iphone7-firmware \
  /etc/initramfs-tools/hooks/hoolock-iphone7-firmware
sudo update-initramfs -u
```

For a manually assembled initramfs, copy the same files below
`/lib/firmware` and preserve the names exactly. Verify the installation and a
Debian initramfs with:

```sh
test -s /lib/firmware/apple/t8010-smartio.bin
test -s /lib/firmware/apple/dfrmtfw-d111-c1f5e-2.bin
test -s /lib/firmware/brcm/BCM.apple,d111.hcd
test "$(find /lib/firmware/brcm -maxdepth 1 \
  -name 'brcmfmac4355-pcie*' -type f | wc -l | tr -d ' ')" = 7
test -s /lib/firmware/regulatory.db
test -s /lib/firmware/regulatory.db.p7s

INITRAMFS="/boot/initrd.img-$(uname -r)"
test -f "$INITRAMFS"
lsinitramfs "$INITRAMFS" | \
  grep -q 'apple/t8010-smartio.bin$'
lsinitramfs "$INITRAMFS" | \
  grep -q 'apple/dfrmtfw-d111-c1f5e-2.bin$'
lsinitramfs "$INITRAMFS" | \
  grep -q 'brcm/BCM.apple,d111.hcd$'
test "$(lsinitramfs "$INITRAMFS" | \
  grep -c 'brcm/brcmfmac4355-pcie')" = 7
lsinitramfs "$INITRAMFS" | grep -q 'regulatory.db$'
lsinitramfs "$INITRAMFS" | grep -q 'regulatory.db.p7s$'
```

If the initramfs is built on another machine, verify its embedded files by
extracting it and comparing the SHA-256 values above. Finding the files only
in the root filesystem is not sufficient for a built-in driver.

## 9. Prepare private SysCfg for the D111-capable m1n1 loader

The firmware container contains requests for calibration, not the private
calibration bytes themselves. Boot it with the D111-capable `idevice` branch
of [`m1n1-ipad7`](https://github.com/Pauli1Go/m1n1-ipad7/tree/idevice) and a
D111-capable kernel from the `dev` branch of
[`HoolockLinux-ipad7`](https://github.com/Pauli1Go/HoolockLinux-ipad7/tree/dev).

During `kboot`, m1n1 reads the following properties from Apple's live Device
Tree and copies them into the Linux Device Tree:

```text
apple,z2-cal-blob
apple,z2-orb-gap-cal-blob
apple,z2-orb-force-cal-blob
apple,z2-shape-accel-cal-blob
```

On the validated iPhone these contain 1024, 992, 1474, and 208 bytes,
respectively. m1n1 validates placeholders and bounds before copying. If any
required value is absent, unresolved, or invalid, it disables the touchscreen
node and continues booting Linux without touch.

This live Device Tree path is specific to D111 touch. Do not add SysCfg to the
touch firmware container and do not reuse the calibrated iPad converter
command.

Wi-Fi, Bluetooth identity, and the ambient-light sensor use a separate SysCfg
path. The common files under `/lib/firmware` do not contain this iPhone's MAC
addresses, Wi-Fi calibration, or CT821 factory calibration. The patched loader
supplies the private `WMac`, `WCAL`, and `LSCI` values through Linux NVMEM and
the `BMac` value as Bluetooth `local-bd-address`, all from the same iPhone's
SysCfg.

The following read-only step runs on the target iPhone under Linux. On the
validated storage layout, SysCfg is exposed as `/dev/nvme0n3`. Confirm both
the block device and its exact size; do not assume the same node on another
layout or device:

```sh
test -b /dev/nvme0n3
test "$(blockdev --getsize64 /dev/nvme0n3)" = 131072

dd if=/dev/nvme0n3 \
  of=/tmp/d111-syscfg.bin \
  bs=131072 \
  count=1 \
  status=progress

test "$(wc -c < /tmp/d111-syscfg.bin | tr -d ' ')" = 131072
sha256sum /tmp/d111-syscfg.bin
```

This `dd` command only reads from NVMe. It does not write to SysCfg, GPT, or
APFS. Copy the result to the development machine and immediately restrict its
permissions:

```sh
IPHONE_ADDRESS=172.16.42.1
scp "root@$IPHONE_ADDRESS:/tmp/d111-syscfg.bin" syscfg.bin
chmod 0600 syscfg.bin
test "$(wc -c < syscfg.bin | tr -d ' ')" = 131072
```

Validate the container structure and create the bounded m1n1 component with
the repository tool:

```sh
python3 tools/make_syscfg_payload.py \
  syscfg.bin \
  m1n1-syscfg.payload
test "$(wc -c < m1n1-syscfg.payload | tr -d ' ')" = 131087
case "$(uname -s)" in
  Darwin) test "$(stat -f '%Lp' m1n1-syscfg.payload)" = 600 ;;
  *) test "$(stat -c '%a' m1n1-syscfg.payload)" = 600 ;;
esac
```

The tool rejects an invalid header or declared size, an out-of-bounds key
table or jumbo value, missing or duplicate D111 `WMac`, `WCAL`, `BMac`, or
`LSCI` records, and malformed LSCI framing or checksum. It does not print the
private values or their hashes. The output is created exclusively with mode
0600 and an existing destination is never overwritten.

Include this component exactly once in a payload for the patched D111 m1n1
loader. The loader reserves a private copy, publishes the `WMac`, `WCAL`, and
`LSCI` NVMEM cells, connects them to the BCM4355 Wi-Fi and CT821 consumers,
and writes `BMac` to the Bluetooth node in the byte order expected by Linux.
Do not install `syscfg.bin` under `/lib/firmware`, do not use an iPad or
another iPhone's dump, and never publish its hash or contents. Both private
filenames are already ignored by this repository.

The public HCD file and the private SysCfg records serve different purposes.
The HCD provides Patchram code; `BMac` provides the device address. Private
Bluetooth RF calibration from `BTRx`, `BTTx`, and `BCAL` is not currently
consumed by Linux.

After confirming the local copy, remove the temporary target-side file:

```sh
ssh "root@$IPHONE_ADDRESS" rm -f /tmp/d111-syscfg.bin
```

Missing D111 `WCAL` allowed the firmware to start but caused a repeated
firmware TRAP during bring-up. Do not treat a created `wlp2s0` interface as a
successful test unless platform calibration was accepted and the firmware
remains stable.

## 10. Verify the running system

After booting the matching kernel, m1n1, Device Tree, and initramfs, verify
the live binding:

```sh
dmesg | grep -E 'apple-z2|SmartIO|touchscreen|brcmfmac|Firmware: BCM4355|Calibration blob|TxCap|Bluetooth: hci0|LSCI|Light sensor'
readlink /sys/bus/spi/devices/spi0.0/driver
grep -A6 -B1 'iPhone9,4 Touchscreen' /proc/bus/input/devices
test "$(basename "$(readlink /sys/bus/pci/devices/0000:02:00.0/driver)")" = \
  brcmfmac
ip link show wlp2s0
test -e /sys/class/bluetooth/hci0
systemctl --no-pager --full status bluetooth.service
bluetoothctl show
IIO_DEVICE="$(grep -l '^ct821$' /sys/bus/iio/devices/iio:device*/name | \
  sed 's,/name$,,')"
test -n "$IIO_DEVICE"
cat "$IIO_DEVICE/in_illuminance_both_raw"
cat "$IIO_DEVICE/in_illuminance_ir_raw"
cat "$IIO_DEVICE/in_illuminance_input"
```

Expected results include:

```text
/sys/bus/spi/drivers/apple-z2
N: Name="iPhone9,4 Touchscreen"
Firmware: BCM4355/10 ... version 9.44.204.0.3.50.45
loaded LSCI ambient-light calibration
Light sensor found.
```

The brcmfmac log must also state that the calibration blob was provided by
the platform and that a TxCap blob was found. Confirm that the exact D111
firmware was installed:

```sh
sha256sum /lib/firmware/apple/dfrmtfw-d111-c1f5e-2.bin
sha256sum /lib/firmware/brcm/BCM.apple,d111.hcd
sha256sum /lib/firmware/brcm/brcmfmac4355-pcie.apple,olaf.bin
sha256sum /lib/firmware/brcm/brcmfmac4355-pcie.apple,olaf.clm_blob
sha256sum /lib/firmware/brcm/brcmfmac4355-pcie.apple,olaf.txcap_blob
sha256sum /lib/firmware/brcm/brcmfmac4355-pcie.apple,olaf-PRNL-*.txt
```

Finally, use `evtest` on the event device identified in
`/proc/bus/input/devices` and perform a short physical touch test. A successful
test must show changing absolute X/Y coordinates, `SYN_REPORT` frames, and
balanced touch-down/touch-up events. Merely finding the firmware file or the
SPI device does not prove that touch is working.

For Wi-Fi, use the distribution's normal NetworkManager or wpa_supplicant
workflow to scan and connect in station mode. A successful test requires a
real association, an assigned address, data transfer, and no subsequent
firmware TRAP or recovery loop. Do not use `nmcli device wifi hotspot` or
reactivate an AP profile on D111: access-point mode is not validated and the
tested AP reconfiguration caused a full system freeze.

This exact SmartIO blob, D11 source hash, generated Z2FW hash, dynamic
calibration path, Wi-Fi source bytes, firmware filenames, and initramfs
placement were used in the validated iPhone 7 Plus boot. `spi0.0` bound to
`apple-z2`, the input device registered as `iPhone9,4 Touchscreen`, and
physical multitouch input was confirmed without Z2, SPI, or touchscreen
errors. BCM4355 station mode remained firmware-crash-free, associated through
NetworkManager, and transferred data successfully. The documented 19H390
Wi-Fi sources are byte-identical to the files used for that test.

The CT821 is exposed as the standard IIO device `ct821`. Its broadband and
infrared raw channels and processed lux value must change plausibly with
ambient light. `iio-sensor-proxy` and GNOME automatic brightness use this IIO
interface without a device-specific userspace daemon. Missing or invalid
`LSCI` calibration must fail the CT821 probe instead of silently producing
uncalibrated values.

The D111 Bluetooth controller is exposed as a normal BlueZ HCI controller.
The kernel powers it through the standard serdev path, switches the Broadcom
controller and host UART to their runtime rates, and loads
`brcm/BCM.apple,d111.hcd` automatically through `request_firmware()`. On the
validated boot it reported `BCM4355C0 Olaf MUR MCC`, firmware build 1324, used
the device-specific address supplied from SysCfg, and had no HCI RX/TX errors.
Discovery, connection, and A2DP audio with AirPods were validated through
ordinary BlueZ userspace without `hciattach`, a manual driver rebind, or a
firmware-path override.

Bluetooth RF calibration is not yet implemented. Until `BTRx`, `BTTx`, and
`BCAL` are consumed, range, transmit power, receive sensitivity, and RF
performance must not be treated as fully calibrated.
