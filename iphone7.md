# Reproducing iPhone 7 Plus/D111 Linux firmware

This document describes how to reproduce the Apple firmware used by
HoolockLinux on the iPhone 7 Plus (`iPhone9,4`, T8010/D111). The documented
combination has been booted on hardware and the touchscreen has been verified
with physical touch input.

The completed installation contains:

```text
/lib/firmware/apple/t8010-smartio.bin
/lib/firmware/apple/dfrmtfw-d111-c1f5e-2.bin
```

This repository does not distribute either Apple firmware file. The commands
below reproduce both from one Apple restore image. The generated D111
container does not contain device-specific calibration: the supported m1n1
loader copies that data from Apple's live Device Tree at every boot.

This guide is specific to the iPhone 7 Plus D111. The smaller iPhone 7 uses
D10 and a different multitouch profile; D10 has not been validated by the
current HoolockLinux port and must not be treated as covered by these steps.
Wi-Fi, Bluetooth, audio, and other iPhone firmware are also outside the scope
of the currently validated port.

Commands are run from the repository root unless stated otherwise.

## Requirements

- [`ipsw`](https://github.com/blacktop/ipsw), tested with version 3.1.696
- Python 3.11
- `curl`
- `shasum` on macOS or an equivalent SHA-256 tool
- Git, `make`, and a C compiler
- a D111-capable HoolockLinux kernel and m1n1 loader
- root access to the target root filesystem or initramfs
- `initramfs-tools` when using the Debian installation method below

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
`0x00088060` bytes long. Extract it with Python 3.11:

```sh
python3.11 - <<'PY'
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

## 5. Install the firmware

Install both files into the target root filesystem using the exact names
requested by the Device Tree and drivers:

```sh
sudo install -d /lib/firmware/apple
sudo install -m 0644 t8010-smartio.bin \
  /lib/firmware/apple/t8010-smartio.bin
sudo install -m 0644 dfrmtfw-d111-c1f5e-2.bin \
  /lib/firmware/apple/dfrmtfw-d111-c1f5e-2.bin
```

The validated kernel builds the Apple Z2 and SmartIO drivers into the kernel,
so their firmware must be present in the early initramfs. Generic dependency
detection can omit firmware for built-in drivers. On Debian, create an
`initramfs-tools` hook containing:

```sh
#!/bin/sh
set -e

case "$1" in
prereqs)
    exit 0
    ;;
esac

. /usr/share/initramfs-tools/hook-functions

copy_file firmware /lib/firmware/apple/t8010-smartio.bin
copy_file firmware /lib/firmware/apple/dfrmtfw-d111-c1f5e-2.bin
```

Save it as `/etc/initramfs-tools/hooks/hoolock-iphone7-firmware`, make it
executable, and rebuild the initramfs:

```sh
sudo chmod 0755 /etc/initramfs-tools/hooks/hoolock-iphone7-firmware
sudo update-initramfs -u
```

For a manually assembled initramfs, copy the same two paths below
`/lib/firmware/apple` and preserve the names exactly. Verify a Debian
initramfs with:

```sh
test -f "/boot/initrd.img-$(uname -r)"
lsinitramfs "/boot/initrd.img-$(uname -r)" | \
  grep -q 'apple/t8010-smartio.bin$'
lsinitramfs "/boot/initrd.img-$(uname -r)" | \
  grep -q 'apple/dfrmtfw-d111-c1f5e-2.bin$'
```

If the initramfs is built on another machine, verify its embedded files by
extracting it and comparing the two SHA-256 values above. Finding the files
only in the root filesystem is not sufficient for a built-in driver.

## 6. Use the D111-capable m1n1 loader

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

There is no SysCfg trailer for D111 touch. Do not copy `/dev/nvme0n3`, append
an iPad `m1n1_syscfg` payload, or publish calibration extracted from the
device.

## 7. Verify the running system

After booting the matching kernel, m1n1, Device Tree, and initramfs, verify
the live binding:

```sh
dmesg | grep -E 'apple-z2|SmartIO|touchscreen|firmware'
readlink /sys/bus/spi/devices/spi0.0/driver
grep -A6 -B1 'iPhone9,4 Touchscreen' /proc/bus/input/devices
```

Expected results include:

```text
/sys/bus/spi/drivers/apple-z2
N: Name="iPhone9,4 Touchscreen"
```

Confirm that the exact D111 firmware was installed:

```sh
sha256sum /lib/firmware/apple/dfrmtfw-d111-c1f5e-2.bin
```

Finally, use `evtest` on the event device identified in
`/proc/bus/input/devices` and perform a short physical touch test. A successful
test must show changing absolute X/Y coordinates, `SYN_REPORT` frames, and
balanced touch-down/touch-up events. Merely finding the firmware file or the
SPI device does not prove that touch is working.

This exact SmartIO blob, D11 source hash, generated Z2FW hash, dynamic
calibration path, firmware filename, and initramfs placement were used in the
validated iPhone 7 Plus boot. `spi0.0` bound to `apple-z2`, the input device
registered as `iPhone9,4 Touchscreen`, and physical multitouch input was
confirmed without Z2, SPI, or touchscreen errors.
