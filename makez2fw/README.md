# makez2fw

`makez2fw` converts an Apple multitouch MTFW image plus the device-specific
SysCfg calibration into the Z2FW container loaded by HoolockLinux's
`apple_z2` driver.

## Build

A C compiler, `make`, and `ar` are required:

```sh
make
```

The resulting executable is `./makez2fw`.

## Usage

```sh
./makez2fw \
  'K1F19,6' \
  J172_Multitouch.mtfw \
  syscfg.bin \
  dfrmtfw-j172-k1f19-6.bin
```

## Origin and licensing

The MTFW, SysCfg, eplist, and qdict support code is derived from
[Project Sandcastle](https://github.com/corellium/projectsandcastle) commit
`03db9c6ae04141eb940f3b9f56d446f50d57fadf` and is distributed under
GPL-2.0-or-later. See `COPYING`.

The converter and parser were extended for the J172 HBPP14/Z2FW format.
The source files, not a prebuilt executable, are provided so the exact tool can
be inspected and rebuilt.

The bundled Mini-XML 3.1 source is Copyright 2003-2019 Michael R Sweet and is
licensed under Apache-2.0. See `mxml-3.1/LICENSE`.

No Apple firmware or device-specific calibration is included.
