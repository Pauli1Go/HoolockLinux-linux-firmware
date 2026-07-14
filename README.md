# HoolockLinux Touch Firmware

Firmware binaries are not distributed here. Extract them from firmware for
your own compatible device and place them in the initramfs as:

```text
/lib/firmware/apple/t8010-smartio.bin
/lib/firmware/apple/dfrmtfw-j172-k1f19-6.bin
```

## Extracting the J172 touch firmware

The tested touch firmware was extracted from the iPadOS 18.7.9 (22H355)
IPSW for `iPad7,12`. With the `ipsw` command-line tool installed, extract the
multitouch IM4P and then its payload:

```sh
mkdir -p extracted

ipsw extract \
  --flat \
  --pattern '.*J172_Multitouch\.im4p$' \
  --output extracted \
  iPad7,12_Restore.ipsw

ipsw img4 im4p extract \
  --output J172_Multitouch.mtfw \
  extracted/J172_Multitouch.im4p
```

The extracted payload used for the tested build is:

```text
cb67cae5956af0ead9f4ffbc2a5e6f2ffdfea667db51e379d24fd3b6713ffbdf  J172_Multitouch.mtfw
```

The Linux firmware container also requires the device-specific 128 KiB
SysCfg data containing the touch calibration. On the tested HoolockLinux
setup this appeared as `/dev/nvme0n3`. Verify both the device and its exact
size before reading it; do not assume that this node is correct on another
storage layout:

```sh
test "$(blockdev --getsize64 /dev/nvme0n3)" = 131072
dd if=/dev/nvme0n3 of=syscfg.bin bs=128K count=1 status=progress
```

Generate the kernel-loadable container with the matching `makez2fw` tool:

```sh
makez2fw \
  'K1F19,6' \
  J172_Multitouch.mtfw \
  syscfg.bin \
  dfrmtfw-j172-k1f19-6.bin
```

`dfrmtfw-j172-k1f19-6.bin` therefore contains data derived from both the
Apple MTFW and the individual device's calibration. The exact tested
`makez2fw` source still needs to be published before this part is fully
reproducible from this repository alone.

The exact extraction source and procedure for `t8010-smartio.bin` is not yet
documented. Do not substitute an unverified SmartIO firmware image.

## Reference hashes

The complete firmware files used for the tested J172 boot had these hashes.
The generated touch container may differ when built with another device's
SysCfg calibration:

```text
71d274a106f5912ed33552ba75ae76cc5081fc7063935ec938f9cb503df38199  t8010-smartio.bin
6b90903c6cb9c223e42a5ce41fc70d3affc93a1cf272bface5918875e7160b7a  dfrmtfw-j172-k1f19-6.bin
```
