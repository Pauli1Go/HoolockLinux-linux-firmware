# Reproducing the iPad7/J172 Linux touch firmware

HoolockLinux requires two firmware files for touch support on the cellular
seventh-generation iPad (`iPad7,12`, T8010/J172):

```text
/lib/firmware/apple/t8010-smartio.bin
/lib/firmware/apple/dfrmtfw-j172-k1f19-6.bin
```

This repository does not distribute Apple firmware or device calibration.
The steps below extract the firmware from Apple's public iPadOS restore image
and read the calibration from the user's own iPad.

The documented reference image is iPadOS 18.7.9 (22H355) for `iPad7,12`.
Commands are intended to be run from the repository root unless a section
explicitly says to run them on the iPad.

## Requirements

- [`ipsw`](https://github.com/blacktop/ipsw) (tested with version 3.1.696)
- Python 3
- `curl`
- `shasum` on macOS or an equivalent SHA-256 tool
- Git, `make`, and a C compiler to build `makez2fw`
- Linux running on the target iPad to read its SysCfg partition

Clone the repository and enter it:

```sh
git clone --depth 1 \
  https://github.com/Pauli1Go/HoolockLinux-linux-touch-firmware.git
cd HoolockLinux-linux-touch-firmware
```

If the repository is already checked out, continue from its root directory.

## 1. Download the restore image

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

## 2. Extract `t8010-smartio.bin`

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

This is a build-specific offset. Do not use it with another iPadOS build.

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

This section runs on the iPad under Linux.

On the tested HoolockLinux storage layout, SysCfg is exposed as
`/dev/nvme0n3`. Confirm the block device and its exact size before reading it;
do not assume that the same node is correct on a different storage layout.

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

Return to the development computer and copy the file into the working
directory:

```sh
scp root@<ipad-address>:/tmp/syscfg.bin .
chmod 0600 syscfg.bin
test "$(wc -c < syscfg.bin | tr -d ' ')" = 131072
```

SysCfg contains device-specific touchscreen calibration. Do not reuse a dump
from another iPad and do not publish it.

## 5. Build and run `makez2fw`

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
expected to differ between devices.

## 6. Install the firmware

Both files must be available when the Apple SIO and `apple_z2` drivers probe.
Install them in the firmware directory used by the root filesystem or early
initramfs:

```sh
sudo install -d /lib/firmware/apple
sudo install -m 0644 t8010-smartio.bin \
  /lib/firmware/apple/t8010-smartio.bin
sudo install -m 0644 dfrmtfw-j172-k1f19-6.bin \
  /lib/firmware/apple/dfrmtfw-j172-k1f19-6.bin
```
