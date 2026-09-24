# libbndl

[libbndl](https://github.com/Bo98/libbndl) reads and writes Criterion/EA
**BUNDLE** archives used in Burnout Paradise and related titles.
BitcoinAgent pins one upstream revision so the parser matches a known tree.

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
| Inspect an archive | `libbndl_inspect` — magic, platform, revision, flags, resource list |
| Filter by type | `libbndl_inspect <file> type TextFile` or `libbndl_types` |
| Look up one resource | `libbndl_lookup` — name or 32-bit hex ID |
| Extract payloads | `libbndl_extract` — `GetBinary` + zlib decompress to a local folder |
| Create / add / replace | `libbndl_create`, `libbndl_add`, `libbndl_replace` — Save as BND2 PC |
| Download an archive | `libbndl_fetch <https-url> [dest]` — public hosts only, size-capped |

Names hash as CRC-32 of the lowercased string, same as
`Bundle::HashResourceName` in the pinned tree.

Supported at this pin:

- **BND2** revision 2 (PC / Xbox 360 / PS3)
- **BNDL** revisions 3–5, with platform detection at `0x4C` (PC),
  `0x58` (Xbox 360), and `0x64` (PS3)
- **Save** writes BND2 revision 2 for PC (the supported `SaveBND2` path).
  A BNDL source is converted on write.

## Limits

- Extract / create payloads are capped at 8 MiB per block.
- Fetches are http(s) only, public hosts, 32 MiB max. Localhost and
  private addresses are refused.
- Extracted bytes are never executed.

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
arch.Save(argv[2]);
```

## Check from this tree (no AWS)

```bash
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl inspect path/to/file.BNDL
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl lookup path/to/file.BNDL 0x12345678
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl types path/to/file.BNDL
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl extract path/to/file.BNDL hello.txt /tmp/out
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl create /tmp/out.bnd2 hello.txt TextFile ./hello.txt
python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl fetch https://example.com/file.BNDL /tmp/file.BNDL
```
