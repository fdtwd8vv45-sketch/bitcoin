# libbndl

[libbndl](https://github.com/Bo98/libbndl) reads Criterion/EA **BUNDLE**
archives used in Burnout Paradise and related titles. BitcoinAgent inspects
those files **read-only** and pins one upstream revision so the parser
matches a known tree.

Pinned commit (non-Xbox BNDL + BNDL v3/v4 improvements):

- Tree: https://github.com/Bo98/libbndl/tree/2b88effe9278dd832f7a1771a472cd4db0dbc072
- Commit: https://github.com/Bo98/libbndl/commit/2b88effe9278dd832f7a1771a472cd4db0dbc072
  (`2b88eff` — *Add support for non-Xbox BNDL*)
- Used by: https://github.com/Bo98/libapt2

Do not follow `master` blindly. Later commits can change the on-disk
layout; this agent stays on the hash above.

## What this agent will do

| Action | How |
| --- | --- |
| Explain the library | `libbndl_overview` |
| Inspect a local archive | `libbndl_inspect` — magic, platform, revision, flags, resource list |
| Look up one resource | `libbndl_lookup` — name or 32-bit hex ID |

Names hash as CRC-32 of the lowercased string, same as
`Bundle::HashResourceName` in the pinned tree.

Supported at this pin:

- **BND2** revision 2 (PC / Xbox 360 / PS3)
- **BNDL** revisions 3–5, with platform detection at `0x4C` (PC),
  `0x58` (Xbox 360), and `0x64` (PS3)

## What this agent will not do

`Save`, `AddResource`, and `ReplaceResource` stay in the C++ library.
BitcoinAgent does not write archives, extract payloads to disk, or
download game files.

To build the upstream library on a machine you control:

```bash
git clone https://github.com/Bo98/libbndl.git
cd libbndl
git checkout 2b88effe9278dd832f7a1771a472cd4db0dbc072
mkdir build && cd build
cmake ..
cmake --build .
```

```c++
#include <libbndl/bundle.hpp>

libbndl::Bundle arch;
arch.Load(argv[1]);
auto ids = arch.ListResourceIDs();
```

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl inspect path/to/file.BNDL
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl lookup path/to/file.BNDL 0x12345678
```

`inspect` and `lookup` take a local filesystem path. They never follow
`http://` URLs.
