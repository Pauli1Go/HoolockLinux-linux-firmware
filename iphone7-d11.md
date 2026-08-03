# Reproducing iPhone 7 Plus/D11 Linux firmware

This document describes how to reproduce the Apple firmware needed by the
HoolockLinux `dt11` branches on the Qualcomm iPhone 7 Plus (`iPhone9,2`,
T8010/D11). The extraction and generated files below have been reproduced
from the verified iOS 15.8.4 restore image. The D11 kernel firmware names
were checked against the `dt11` Device Tree, and the `sven` selection was
checked against Project Sandcastle's PCI-port selection logic.

Unlike the [D111 guide](iphone7.md), this combination has not yet completed a
D11 hardware test. The first device owner must still verify the OTP-selected
Wi-Fi profile, select the matching Bluetooth HCD, and supply private
calibration from that same phone. Do not present static extraction checks as
a successful hardware test.

The completed D11 installation contains:

```text
/lib/firmware/apple/t8010-smartio.bin
/lib/firmware/apple/dfrmtfw-d11-c1f5e-2.bin
/lib/firmware/brcm/BCM.apple,d11.hcd
/lib/firmware/brcm/brcmfmac4355-pcie.apple,d11.bin
/lib/firmware/brcm/brcmfmac4355-pcie.apple,d11.clm_blob
/lib/firmware/brcm/brcmfmac4355-pcie.apple,d11.txcap_blob
/lib/firmware/brcm/brcmfmac4355-pcie.apple,d11-PRNL-*.txt
```

The board-qualified D11 Wi-Fi names are intentional. D111 uses the `olaf`
firmware family while D11 uses `sven`. Installing `sven` under D11-qualified
names allows one root filesystem to retain the existing D111 `olaf` files.
Renaming an `olaf` file does not turn it into D11 firmware.

This repository does not distribute Apple firmware, Wi-Fi NVRAM, Bluetooth
Patchram, or private device calibration. Common firmware is reproduced from
Apple's restore image. `WMac`, `WCAL`, `BMac`, touch calibration, and ambient
light calibration must come from the phone that will boot the payload. Never
publish a private SysCfg image or payload.

Commands are run from the repository root unless stated otherwise.

## Requirements

- [`ipsw`](https://github.com/blacktop/ipsw), tested with version 3.1.696
- Python 3
- `curl`
- `shasum` on macOS or an equivalent SHA-256 tool
- Git, `make`, and a C compiler to build `makez2fw` and `hcdpack`
- the `dt11` branches of the HoolockLinux kernel and m1n1 repositories
- root access to the target root filesystem or initramfs
- a serial console or persistent boot log for the first OTP-identification boot

Clone the repository and enter it:

```sh
git clone --depth 1 \
  https://github.com/Pauli1Go/HoolockLinux-linux-firmware.git
cd HoolockLinux-linux-firmware
```

## 1. Download and verify the shared iPhone 7 Plus restore image

D11 and D111 share the `iPhone9,2_4` iOS filesystem. Download the exact iOS
15.8.4 (19H390) restore image already used by the hardware-tested D111 guide:

[Download iOS 15.8.4 (19H390) for iPhone 7 Plus](https://updates.cdn-apple.com/2025WinterSeed/fullrestores/062-48481/770AB33F-5F75-44C0-9E23-65E8648D76C6/iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw)

```sh
curl --fail --location --continue-at - \
  --output iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw \
  'https://updates.cdn-apple.com/2025WinterSeed/fullrestores/062-48481/770AB33F-5F75-44C0-9E23-65E8648D76C6/iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw'

test "$(wc -c < iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw | tr -d ' ')" = \
  5563988045
shasum -a 256 iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw
```

Expected SHA-256:

```text
bcb69450536a3909f3b6a49f278dfe634e8bfa9dc825f6ab5d1116fa569e657d
```

Stop if the size or hash differs. The offsets and output hashes below are
only asserted for this exact restore image.

## 2. Extract the common T8010 SmartIO firmware

Extract the D11 kernelcache:

```sh
ipsw extract \
  --kernel \
  --device iPhone9,2 \
  --output smartio-kernel \
  iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw

KERNELCACHE='smartio-kernel/19H390__iPhone9,2/kernelcache.release.iPhone9,2_4'
test "$(wc -c < "$KERNELCACHE" | tr -d ' ')" = 44924928
shasum -a 256 "$KERNELCACHE"
```

Expected kernelcache SHA-256:

```text
3588eeca5ec84024fa11aeef1dc5a2f2e3d092fb82eff3a9d3e5a80f2606ec1d
```

Extract the native `AppleT8010SmartIO` image at the verified offset:

```sh
python3 - <<'PY'
from pathlib import Path

source = Path(
    "smartio-kernel/19H390__iPhone9,2/"
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

This is the same T8010 SmartIO image used by D111. Its deterministic
extraction is verified, but D11 runtime use remains part of the hardware test.

## 3. Build the D11 multitouch container

Extract the shared D11 property list:

```sh
ipsw extract \
  --files \
  --flat \
  --pattern '(^|/)usr/share/firmware/multitouch/D11\.mtprops$' \
  --output touch \
  iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw

TOUCH_SOURCE='touch/19H390__iPhone9,2_4/D11.mtprops'
test -f "$TOUCH_SOURCE"
test "$(wc -c < "$TOUCH_SOURCE" | tr -d ' ')" = 116503
shasum -a 256 "$TOUCH_SOURCE"
grep -q '<key>C1F5E,2</key>' "$TOUCH_SOURCE"
```

Expected source SHA-256:

```text
7f9b16b749dd0f3e12633ce5140220ea89317006dc0278b24cf2d815578e3ff6
```

Build the converter and generate the D11-named container. Dynamic calibration
keeps private calibration out of the common firmware file; the matching m1n1
branch publishes calibration from Apple's live Device Tree at boot.

```sh
make -C makez2fw

makez2fw/makez2fw \
  --dynamic-calibration \
  'C1F5E,2' \
  "$TOUCH_SOURCE" \
  dfrmtfw-d11-c1f5e-2.bin

test "$(wc -c < dfrmtfw-d11-c1f5e-2.bin | tr -d ' ')" = 76724
shasum -a 256 dfrmtfw-d11-c1f5e-2.bin
```

Expected SHA-256:

```text
57f094f2afbc21c3eca511f5b5d0a90e276789a0a5e8f770528e682fdfa660d6
```

The generated bytes match the D111 container because both Plus variants use
the same property-list personality and dynamic-calibration layout. The D11
filename is nevertheless required by the D11 Device Tree.

## 4. Extract the D11 `sven` BCM4355 Wi-Fi family

Project Sandcastle selects `olaf` for the D111 Wi-Fi device on PCIe root port
2 and `sven` for the D11 device on root port 3. Both families are present in
the shared Apple filesystem. Extract only the normal `sven` files and all
four PRNL names that the supported OTP profiles may request:

```sh
ipsw extract \
  --files \
  --flat \
  --pattern '(^|/)usr/share/firmware/wifi/C-4355__s-C0/(sven\.(trx|clmb|txcb)|P-sven_M-PRNL_V-(m__m-(5\.3|5\.7)|u__m-(5\.3|5\.9))\.txt)$' \
  --output wifi \
  iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw

WIFI_SOURCE='wifi/19H390__iPhone9,2_4/usr/share/firmware/wifi/C-4355__s-C0'
test "$(find "$WIFI_SOURCE" -maxdepth 1 -type f | wc -l | tr -d ' ')" = 7
```

Verify each source file:

| File | Size | SHA-256 |
| --- | ---: | --- |
| `sven.trx` | 746960 | `ed8c7bc41643ac230274cd027fc052bf29de6857488fbf93625258fbdd02149a` |
| `sven.clmb` | 9248 | `fed3efc9c57d38932899549dc325a9bbebedcbc6110057ed87151ba325d947d3` |
| `sven.txcb` | 632 | `60488ea1a37a2844ac196db7a5a10cd4ded3b4e80622cbecb9825623674f670e` |
| `P-sven_M-PRNL_V-m__m-5.3.txt` | 5167 | `3fd90d00aad4ac69d7c11436e7e11dab02a8f13f55a406a5fc14056d5b902836` |
| `P-sven_M-PRNL_V-m__m-5.7.txt` | 5167 | `3fd90d00aad4ac69d7c11436e7e11dab02a8f13f55a406a5fc14056d5b902836` |
| `P-sven_M-PRNL_V-u__m-5.3.txt` | 5172 | `bc0cbbc55ed2238bfe708c40fdbb3529947480197825642344c1998096cb2e0e` |
| `P-sven_M-PRNL_V-u__m-5.9.txt` | 5172 | `bc0cbbc55ed2238bfe708c40fdbb3529947480197825642344c1998096cb2e0e` |

The equal hashes within each vendor pair do not make the names interchangeable:
the driver constructs its request from the module's OTP vendor and version.
Install all four NVRAM names so the real module selects its own file.

Stage the files with D11-qualified names:

```sh
install -d generated-d11/brcm
install -m 0644 "$WIFI_SOURCE/sven.trx" \
  generated-d11/brcm/brcmfmac4355-pcie.apple,d11.bin
install -m 0644 "$WIFI_SOURCE/sven.clmb" \
  generated-d11/brcm/brcmfmac4355-pcie.apple,d11.clm_blob
install -m 0644 "$WIFI_SOURCE/sven.txcb" \
  generated-d11/brcm/brcmfmac4355-pcie.apple,d11.txcap_blob
install -m 0644 "$WIFI_SOURCE/P-sven_M-PRNL_V-m__m-5.3.txt" \
  generated-d11/brcm/brcmfmac4355-pcie.apple,d11-PRNL-m-5.3.txt
install -m 0644 "$WIFI_SOURCE/P-sven_M-PRNL_V-m__m-5.7.txt" \
  generated-d11/brcm/brcmfmac4355-pcie.apple,d11-PRNL-m-5.7.txt
install -m 0644 "$WIFI_SOURCE/P-sven_M-PRNL_V-u__m-5.3.txt" \
  generated-d11/brcm/brcmfmac4355-pcie.apple,d11-PRNL-u-5.3.txt
install -m 0644 "$WIFI_SOURCE/P-sven_M-PRNL_V-u__m-5.9.txt" \
  generated-d11/brcm/brcmfmac4355-pcie.apple,d11-PRNL-u-5.9.txt
```

The IPSW also contains `sven-CN` and `sven-JP`. The current Sandcastle D11
selection uses normal `sven`; the regional alternatives have not been
validated with the HoolockLinux D11 port and must not be selected merely from
the phone's sales region.

## 5. Extract both candidate D11 Bluetooth images

The BCM4355C0 Patchram pack is embedded in `BlueTool`:

```sh
ipsw extract \
  --files \
  --pattern '^usr/sbin/BlueTool$' \
  --output bluetooth \
  iPhone_5.5_P3_15.8.4_19H390_Restore.ipsw

BLUETOOL='bluetooth/19H390__iPhone9,2_4/usr/sbin/BlueTool'
test -f "$BLUETOOL"
test "$(wc -c < "$BLUETOOL" | tr -d ' ')" = 9710640
shasum -a 256 "$BLUETOOL"
```

Expected SHA-256:

```text
78115abe9705d30596768231d2f1587bf68670f6a7a2d1db7d88620aa54cca8d
```

Build `hcdpack` from the pinned Project Sandcastle revision:

```sh
git clone https://github.com/corellium/projectsandcastle.git
git -C projectsandcastle checkout \
  03db9c6ae04141eb940f3b9f56d446f50d57fadf
make -C projectsandcastle/hcdpack \
  CFLAGS='-O2 -Wall -I. -D_DARWIN_C_SOURCE'
```

Generate both possible vendor images. The profile version selects the same
Patchram image within one vendor, but the Murata and USI images differ:

```sh
projectsandcastle/hcdpack/hcdpack \
  "$BLUETOOL" \
  'C-4355__s-C0' \
  sven \
  'M-PRNL_V-m__m-5.7' \
  BCM.apple,d11.sven-murata.hcd

projectsandcastle/hcdpack/hcdpack \
  "$BLUETOOL" \
  'C-4355__s-C0' \
  sven \
  'M-PRNL_V-u__m-5.9' \
  BCM.apple,d11.sven-usi.hcd
```

Expected outputs:

| File | Size | SHA-256 |
| --- | ---: | --- |
| `BCM.apple,d11.sven-murata.hcd` | 92702 | `e8c5dbea024e84434a10411d8533d62cac675fbb1bab44206108a56b6fb59434` |
| `BCM.apple,d11.sven-usi.hcd` | 92702 | `3bce88460c018ee2175de900cb6656c71225d6222442c229eff9462ff941f85b` |

Do not guess between these files and do not use the D111 `olaf` HCD. The
Bluetooth driver requests only `brcm/BCM.apple,d11.hcd`, so it cannot select
the vendor image by itself.

## 6. Identify the OTP profile on the first D11 boot

The common files can be prepared without the phone, but the final HCD choice
requires the real BCM4355 OTP. Keep both candidate HCDs outside the final
firmware name for the first diagnostic boot. Install all four D11 NVRAM files
from section 4 and enable brcmfmac dynamic debug before its first probe.

For a modular brcmfmac build, add this kernel command-line parameter:

```text
brcmfmac.dyndbg=+p
```

For a built-in brcmfmac build, use:

```text
dyndbg="file drivers/net/wireless/broadcom/brcm80211/brcmfmac/pcie.c +p"
```

Capture the complete boot log and find the parsed OTP line:

```sh
dmesg | grep 'OTP: module='
```

Expected shape, with values supplied by the actual module:

```text
OTP: module=PRNL vendor=m version=5.7
```

Select the HCD only from that result:

- `vendor=m`: install `BCM.apple,d11.sven-murata.hcd`
- `vendor=u`: install `BCM.apple,d11.sven-usi.hcd`
- any other module, vendor, chip, or revision: stop and extract the exact
  profile identified by that hardware; neither candidate is validated

Install the selected image under the exact name requested by the D11 Device
Tree, then rebuild the initramfs:

```sh
sudo install -d /lib/firmware/brcm
sudo install -m 0644 BCM.apple,d11.sven-murata.hcd \
  /lib/firmware/brcm/BCM.apple,d11.hcd
sudo update-initramfs -u
```

The example command is for `vendor=m`; substitute the USI source only after
observing `vendor=u`.

## 7. Install the remaining common and D11 files

```sh
sudo install -d /lib/firmware/apple /lib/firmware/brcm
sudo install -m 0644 t8010-smartio.bin \
  /lib/firmware/apple/t8010-smartio.bin
sudo install -m 0644 dfrmtfw-d11-c1f5e-2.bin \
  /lib/firmware/apple/dfrmtfw-d11-c1f5e-2.bin
sudo install -m 0644 generated-d11/brcm/* \
  /lib/firmware/brcm/
```

The repository's current `hoolock-iphone7-firmware` initramfs hook is
D111-specific and must not be claimed as D11-compatible. Until that hook is
generalized and tested, explicitly inspect the generated initramfs and prove
that every D11 file listed at the top of this guide is present.

## 8. Supply private calibration from the same D11

The firmware above is not a replacement for the phone's private SysCfg. The
D11 owner must obtain SysCfg from that same phone using an authorized local
method and keep it private. Do not reuse a D111 SysCfg or another D11's file.

The current m1n1 payload format expects the complete bounded SysCfg image and
uses its `WMac`, `WCAL`, `BMac`, and `LSCI` records. The live Apple Device Tree
provides D11 touch calibration separately. Before the first functional test,
verify in the runtime Device Tree that m1n1 published:

- the Wi-Fi calibration cell and MAC address from this phone
- the ambient-light `LSCI` calibration cell
- the Bluetooth address from `BMac`
- all four D11 touch dynamic-calibration providers

The existing payload generator currently uses D111 wording. Its binary
format is common, but D11 input has not yet been validated on hardware. If it
rejects the D11 SysCfg or any required record is absent, stop; do not weaken
validation and do not fabricate a record.
