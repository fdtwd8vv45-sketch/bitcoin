"""Criterion/EA BUNDLE tools pinned to libbndl 2b88eff.

Matches Bo98/libbndl commit 2b88effe9278dd832f7a1771a472cd4db0dbc072
(non-Xbox BNDL plus BNDL v3/v4 improvements). Covers the pinned API:
inspect, lookup, list-by-type, GetBinary extract, Save / AddResource /
ReplaceResource (BND2 PC), and optional HTTP(S) fetch of an archive.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import struct
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from agent_state import reject_secrets
from optional_tool import tool

PINNED_COMMIT = "2b88effe9278dd832f7a1771a472cd4db0dbc072"
REPO_URL = "https://github.com/Bo98/libbndl"
TREE_URL = f"{REPO_URL}/tree/{PINNED_COMMIT}"
COMMIT_URL = f"{REPO_URL}/commit/{PINNED_COMMIT}"
LIBAPT2_URL = "https://github.com/Bo98/libapt2"
BUILD_COMMANDS = "mkdir build && cd build && cmake .. && cmake --build ."

MAGIC_BNDL = b"bndl"
MAGIC_BND2 = b"bnd2"

PLATFORM_PC = 1
PLATFORM_XBOX360 = 2 << 24
PLATFORM_PS3 = 3 << 24
PLATFORM_NAMES = {
    PLATFORM_PC: "PC (or PS4/XB1)",
    PLATFORM_XBOX360: "Xbox 360",
    PLATFORM_PS3: "PS3",
}

FLAG_COMPRESSED = 1
FLAG_UNUSED1 = 2
FLAG_UNUSED2 = 4
FLAG_HAS_RST = 8

RST_RESOURCE_ID = 0xC039284A
BND2_HEADER_SIZE = 0x30
BND2_ENTRY_SIZE = 64
MAX_LIST_ENTRIES = 200
MAX_PARSE_ENTRIES = 10_000
MAX_TABLE_BYTES = 2_000_000
MAX_RST_BYTES = 256_000
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024
MAX_FETCH_BYTES = 32 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 15
HEADER_PREFIX = 256

RESOURCE_TYPES: dict[int, str] = {
    0x00: "Raster",
    0x01: "Material",
    0x02: "ResourceMesh",
    0x03: "TextFile",
    0x04: "DrawIndexParams",
    0x05: "IndexBuffer",
    0x06: "MeshState",
    0x09: "VertexBuffer",
    0x0A: "VertexDesc",
    0x0B: "MaterialCRC32",
    0x0C: "Renderable",
    0x0D: "MaterialTechnique",
    0x0E: "TextureState",
    0x0F: "MaterialState",
    0x10: "DepthStencilState",
    0x11: "RasterizerState",
    0x12: "ShaderProgramBuffer",
    0x14: "ShaderParameter",
    0x15: "RenderableAssembly",
    0x16: "Debug",
    0x17: "KdTree",
    0x18: "VoiceHierarchy",
    0x19: "Snr",
    0x1A: "InterpreterData",
    0x1B: "AttribSysSchema",
    0x1C: "AttribSysVault",
    0x1D: "EntryList",
    0x1E: "AptDataHeader",
    0x1F: "GuiPopup",
    0x21: "Font",
    0x22: "LuaCode",
    0x23: "InstanceList",
    0x24: "CollisionMeshData",
    0x25: "IDList",
    0x26: "InstanceCollisionList",
    0x27: "Language",
    0x28: "SatNavTile",
    0x29: "SatNavTileDirectory",
    0x2A: "Model",
    0x2B: "RwColourCube",
    0x2C: "HudMessage",
    0x2D: "HudMessageList",
    0x2E: "HudMessageSequence",
    0x2F: "HudMessageSequenceDictionary",
    0x30: "WorldPainter2D",
    0x31: "PFXHookBundle",
    0x32: "Shader",
    0x40: "RawFile",
    0x41: "ICETakeDictionary",
    0x42: "VideoData",
    0x43: "PolygonSoupList",
    0x45: "CommsToolListDefinition",
    0x46: "CommsToolList",
    0x50: "BinaryFile",
    0x51: "AnimationCollection",
    0xA000: "Registry",
    0xA020: "GenericRwacWaveContent",
    0xA021: "GinsuWaveContent",
    0xA022: "AemsBank",
    0xA023: "Csis",
    0xA024: "Nicotine",
    0xA025: "Splicer",
    0xA026: "FreqContent",
    0xA027: "VoiceHierarchyCollection",
    0xA028: "GenericRwacReverbIRContent",
    0xA029: "SnapshotData",
    0xB000: "ZoneList",
    0x10000: "LoopModel",
    0x10001: "AISections",
    0x10002: "TrafficData",
    0x10003: "Trigger",
    0x10004: "DeformationModel",
    0x10005: "VehicleList",
    0x10006: "GraphicsSpec",
    0x10007: "PhysicsSpec",
    0x10008: "ParticleDescriptionCollection",
    0x10009: "WheelList",
    0x1000A: "WheelGraphicsSpec",
    0x1000B: "TextureNameMap",
    0x1000C: "ICEList",
    0x1000D: "ICEData",
    0x1000E: "Progression",
    0x1000F: "PropPhysics",
    0x10010: "PropGraphicsList",
    0x10011: "PropInstanceData",
    0x10012: "BrnEnvironmentKeyframe",
    0x10013: "BrnEnvironmentTimeLine",
    0x10014: "BrnEnvironmentDictionary",
    0x10015: "GraphicsStub",
    0x10016: "StaticSoundMap",
    0x10018: "StreetData",
    0x10019: "BrnVFXMeshCollection",
    0x1001A: "MassiveLookupTable",
    0x1001B: "VFXPropCollection",
    0x1001C: "StreamedDeformationSpec",
    0x1001D: "ParticleDescription",
    0x1001E: "PlayerCarColours",
    0x1001F: "ChallengeList",
    0x10020: "FlaptFile",
    0x10021: "ProfileUpgrade",
    0x10023: "VehicleAnimation",
    0x10024: "BodypartRemapping",
    0x10025: "LUAList",
    0x10026: "LUAScript",
    0x11000: "BkSoundWeapon",
    0x11001: "BkSoundGunsu",
    0x11002: "BkSoundBulletImpact",
    0x11003: "BkSoundBulletImpactList",
    0x11004: "BkSoundBulletImpactStream",
}

TYPE_BY_NAME = {name.lower(): value for value, name in RESOURCE_TYPES.items()}

_PATH_TOKEN = re.compile(r"[^\s]+")
_RESOURCE_TOKEN = re.compile(r"^(0x)?[0-9a-fA-F]{1,8}$")
_STOPWORDS = {
    "a",
    "an",
    "add",
    "archive",
    "bnd2",
    "bndl",
    "bundle",
    "create",
    "extract",
    "fetch",
    "file",
    "inspect",
    "libbndl",
    "list",
    "lookup",
    "of",
    "on",
    "open",
    "read",
    "replace",
    "show",
    "the",
    "this",
    "type",
    "types",
}


class BundleError(ValueError):
    """Malformed or unsupported BUNDLE archive."""


@dataclass
class BlockInfo:
    uncompressed_size: int = 0
    uncompressed_alignment: int = 0
    compressed_size: int = 0
    data_offset: int = 0


@dataclass
class ResourceEntry:
    resource_id: int
    resource_type: int
    checksum: int = 0
    dependencies: int = 0
    name: str = ""
    type_name: str = ""
    blocks: list[BlockInfo] = field(default_factory=lambda: [BlockInfo(), BlockInfo(), BlockInfo()])


@dataclass
class BundleInfo:
    source: str
    magic: str
    revision: int
    platform: int
    flags: int
    file_size: int
    entries: list[ResourceEntry]
    parsed_entries: int
    truncated: bool = False
    raw: bytes = b""
    big_endian: bool = False


class BinaryCursor:
    def __init__(self, data: bytes, pos: int = 0, big_endian: bool = False) -> None:
        self.data = data
        self.pos = pos
        self.big_endian = big_endian

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def seek(self, pos: int) -> None:
        if pos < 0 or pos > len(self.data):
            raise BundleError("seek out of range")
        self.pos = pos

    def skip(self, n: int) -> None:
        self.seek(self.pos + n)

    def read(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise BundleError("truncated read")
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def read_u16(self) -> int:
        fmt = ">H" if self.big_endian else "<H"
        return struct.unpack(fmt, self.read(2))[0]

    def read_u32(self) -> int:
        fmt = ">I" if self.big_endian else "<I"
        return struct.unpack(fmt, self.read(4))[0]

    def read_u64(self) -> int:
        fmt = ">Q" if self.big_endian else "<Q"
        return struct.unpack(fmt, self.read(8))[0]


def _read_at(data: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise BundleError("truncated archive")
    return data[offset : offset + size]


def _le_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def resource_type_name(resource_type: int) -> str:
    return RESOURCE_TYPES.get(resource_type, f"Unknown(0x{resource_type:X})")


def platform_name(platform: int) -> str:
    return PLATFORM_NAMES.get(platform, f"Unknown(0x{platform:08X})")


def hash_resource_name(name: str) -> int:
    """CRC-32 of the lowercased resource name (libbndl HashResourceName)."""
    return zlib.crc32(name.lower().encode("utf-8")) & 0xFFFFFFFF


def flag_names(flags: int) -> list[str]:
    names: list[str] = []
    if flags & FLAG_COMPRESSED:
        names.append("Compressed")
    if flags & FLAG_UNUSED1:
        names.append("UnusedFlag1")
    if flags & FLAG_UNUSED2:
        names.append("UnusedFlag2")
    if flags & FLAG_HAS_RST:
        names.append("HasResourceStringTable")
    leftover = flags & ~(FLAG_COMPRESSED | FLAG_UNUSED1 | FLAG_UNUSED2 | FLAG_HAS_RST)
    if leftover:
        names.append(f"Other(0x{leftover:X})")
    return names or ["none"]


def map_bndl_block_to_bnd2(platform: int, block: int) -> int:
    """Map a BNDL file-block index onto the three BND2 blocks.

    Copied from Bundle::MapBNDLBlockToBND2 at the pinned commit.
    """
    if platform == PLATFORM_PC:
        return -1 if block >= 3 else block
    if platform == PLATFORM_XBOX360:
        if block == 1 or block >= 4:
            return -1
        return 0 if block == 0 else block - 1
    if platform == PLATFORM_PS3:
        if 1 <= block <= 3 or block >= 6:
            return -1
        return 0 if block == 0 else block - 3
    return -1


def _bndl_block_count(platform: int) -> int:
    if platform == PLATFORM_XBOX360:
        return 5
    if platform == PLATFORM_PS3:
        return 6
    return 4


def _probe_bndl_platform(header: bytes) -> int:
    # 2b88eff: scan 0x4C (PC), 0x58 (Xbox 360), 0x64 (PS3) instead of Xbox-only.
    for offset in (0x4C, 0x58, 0x64):
        if offset + 4 > len(header):
            continue
        platform = _le_u32(header, offset)
        if platform in PLATFORM_NAMES:
            return platform
    return 0


def _parse_rst_xml(raw: str) -> dict[int, tuple[str, str]]:
    xml = raw
    if xml.startswith("</ResourceStringTable>"):
        xml = "<" + xml[2:]
    broken = xml.find("</ResourceStringTable>\n\t")
    if broken != -1:
        xml = xml[:broken] + xml[broken + 23 :]
    start = xml.find("<ResourceStringTable")
    if start == -1:
        return {}
    end = xml.find("</ResourceStringTable>")
    snippet = xml[start:] if end == -1 else xml[start : end + len("</ResourceStringTable>")]
    try:
        root = ET.fromstring(snippet)
    except ET.ParseError:
        return {}
    out: dict[int, tuple[str, str]] = {}
    for node in root.findall("Resource"):
        raw_id = (node.get("id") or "").strip()
        if not raw_id:
            continue
        try:
            resource_id = int(raw_id, 16)
        except ValueError:
            continue
        out[resource_id] = (node.get("name") or "", node.get("type") or "")
    return out


def _apply_debug_info(entries: list[ResourceEntry], debug: dict[int, tuple[str, str]]) -> None:
    for entry in entries:
        if entry.resource_id in debug:
            entry.name, entry.type_name = debug[entry.resource_id]


def _read_block(data: bytes, block: BlockInfo, *, compressed: bool) -> bytes:
    read_size = block.compressed_size if compressed and block.compressed_size else block.uncompressed_size
    if read_size <= 0:
        return b""
    if read_size > MAX_PAYLOAD_BYTES:
        raise BundleError(f"block is larger than the {MAX_PAYLOAD_BYTES} byte extract cap")
    raw = _read_at(data, block.data_offset, read_size)
    if compressed and block.compressed_size > 0:
        try:
            out = zlib.decompress(raw)
        except zlib.error as exc:
            raise BundleError(f"zlib decompress failed: {exc}") from exc
        if block.uncompressed_size and len(out) != block.uncompressed_size:
            raise BundleError("decompressed size does not match the archive header")
        return out
    return raw


def _parse_bnd2_rst(data: bytes, rst_offset: int) -> dict[int, tuple[str, str]]:
    if rst_offset <= 0 or rst_offset >= len(data):
        return {}
    chunk = data[rst_offset : rst_offset + MAX_RST_BYTES]
    nul = chunk.find(b"\x00")
    if nul != -1:
        chunk = chunk[:nul]
    try:
        text = chunk.decode("utf-8", errors="replace")
    except Exception:
        return {}
    return _parse_rst_xml(text)


def parse_bnd2(data: bytes, source: str) -> BundleInfo:
    if len(data) < BND2_HEADER_SIZE:
        raise BundleError("BND2 header is truncated")
    cur = BinaryCursor(data)
    magic = cur.read(4)
    if magic != MAGIC_BND2:
        raise BundleError("not a BND2 archive")
    revision = cur.read_u32()
    platform = cur.read_u32()
    cur.big_endian = platform != PLATFORM_PC
    if cur.big_endian:
        revision = struct.unpack(">I", struct.pack("<I", revision))[0]
    if revision != 2:
        raise BundleError(f"unsupported BND2 revision {revision} (libbndl expects 2)")
    rst_offset = cur.read_u32()
    num_entries = cur.read_u32()
    id_block_offset = cur.read_u32()
    file_block_offsets = [cur.read_u32(), cur.read_u32(), cur.read_u32()]
    flags = cur.read_u32()
    if num_entries > MAX_PARSE_ENTRIES:
        raise BundleError(f"refusing {num_entries} entries (cap {MAX_PARSE_ENTRIES})")
    table_size = num_entries * BND2_ENTRY_SIZE
    if table_size > MAX_TABLE_BYTES:
        raise BundleError("ID block is larger than the inspect cap")
    table = _read_at(data, id_block_offset, table_size)
    table_cur = BinaryCursor(table, big_endian=cur.big_endian)
    entries: list[ResourceEntry] = []
    for _ in range(num_entries):
        resource_id = table_cur.read_u64() & 0xFFFFFFFF
        checksum = table_cur.read_u64() & 0xFFFFFFFF
        blocks = []
        for _block in range(3):
            packed = table_cur.read_u32()
            blocks.append(
                BlockInfo(
                    uncompressed_size=packed & ~(0xF << 28),
                    uncompressed_alignment=1 << (packed >> 28) if packed >> 28 < 32 else 0,
                )
            )
        for block in blocks:
            block.compressed_size = table_cur.read_u32()
        rels = [table_cur.read_u32() for _ in range(3)]
        for index, block in enumerate(blocks):
            block.data_offset = file_block_offsets[index] + rels[index]
        table_cur.read_u32()
        resource_type = table_cur.read_u32()
        dependencies = table_cur.read_u16()
        table_cur.skip(2)
        entries.append(
            ResourceEntry(
                resource_id=resource_id,
                resource_type=resource_type,
                checksum=checksum,
                dependencies=dependencies,
                blocks=blocks,
            )
        )
    debug: dict[int, tuple[str, str]] = {}
    if flags & FLAG_HAS_RST:
        debug = _parse_bnd2_rst(data, rst_offset)
        _apply_debug_info(entries, debug)
    return BundleInfo(
        source=source,
        magic="BND2",
        revision=revision,
        platform=platform,
        flags=flags,
        file_size=len(data),
        entries=entries,
        parsed_entries=len(entries),
        raw=data,
        big_endian=cur.big_endian,
    )


def parse_bndl(data: bytes, source: str) -> BundleInfo:
    if len(data) < 0x50:
        raise BundleError("BNDL header is truncated")
    prefix = data[: max(HEADER_PREFIX, min(len(data), 256))]
    if prefix[:4] != MAGIC_BNDL:
        raise BundleError("not a BNDL archive")
    platform = _probe_bndl_platform(prefix)
    if platform == 0:
        raise BundleError("BNDL platform not recognized (need PC, Xbox 360, or PS3 at 0x4C/0x58/0x64)")
    cur = BinaryCursor(prefix, 4, big_endian=platform != PLATFORM_PC)
    revision = cur.read_u32()
    if revision < 3 or revision > 5:
        raise BundleError(f"unsupported BNDL revision {revision} (libbndl 2b88eff accepts 3-5)")
    num_entries = cur.read_u32()
    blocks = _bndl_block_count(platform)
    data_block_sizes = []
    for _ in range(blocks):
        data_block_sizes.append(cur.read_u32())
        cur.read_u32()
    cur.skip(4 * blocks)
    id_list_offset = cur.read_u32()
    id_table_offset = cur.read_u32()
    cur.read_u32()
    cur.read_u32()
    saved = cur.big_endian
    cur.big_endian = False
    verified = cur.read_u32()
    cur.big_endian = saved
    if verified != platform:
        raise BundleError("BNDL platform field mismatch")
    compressed = 0
    uncomp_info_offset = 0
    if revision >= 4:
        compressed = cur.read_u32()
        cur.read_u32()
        uncomp_info_offset = cur.read_u32()
    if revision >= 5:
        cur.read_u32()
        cur.read_u32()
    if num_entries > MAX_PARSE_ENTRIES:
        raise BundleError(f"refusing {num_entries} entries (cap {MAX_PARSE_ENTRIES})")
    id_list = BinaryCursor(
        _read_at(data, id_list_offset, num_entries * 8),
        big_endian=platform != PLATFORM_PC,
    )
    resource_ids = [id_list.read_u64() & 0xFFFFFFFF for _ in range(num_entries)]
    entry_size = 12 + blocks * 20
    table = BinaryCursor(
        _read_at(data, id_table_offset, num_entries * entry_size),
        big_endian=platform != PLATFORM_PC,
    )
    entries: list[ResourceEntry] = []
    for resource_id in resource_ids:
        table.skip(4)
        dep_offset = table.read_u32()
        resource_type = table.read_u32()
        block_infos = [BlockInfo(), BlockInfo(), BlockInfo()]
        for block in range(blocks):
            mapped = map_bndl_block_to_bnd2(platform, block)
            if mapped == -1:
                table.skip(8)
                continue
            size = table.read_u32()
            alignment = table.read_u32()
            if compressed:
                block_infos[mapped].compressed_size = size
            else:
                block_infos[mapped].uncompressed_size = size
                block_infos[mapped].uncompressed_alignment = alignment
        data_block_start = 0
        for block in range(blocks):
            if block > 0:
                data_block_start += data_block_sizes[block - 1]
            rel = table.read_u32()
            table.read_u32()
            mapped = map_bndl_block_to_bnd2(platform, block)
            if mapped != -1:
                block_infos[mapped].data_offset = rel + data_block_start
        table.skip(4 * blocks)
        dependencies = 0
        if dep_offset and dep_offset + 4 <= len(data):
            dep_cur = BinaryCursor(
                data[dep_offset : dep_offset + 4],
                big_endian=platform != PLATFORM_PC,
            )
            dependencies = dep_cur.read_u32()
        entries.append(
            ResourceEntry(
                resource_id=resource_id,
                resource_type=resource_type,
                dependencies=dependencies,
                blocks=block_infos,
            )
        )
    flags = FLAG_COMPRESSED if compressed else 0
    if compressed and uncomp_info_offset:
        info = BinaryCursor(
            _read_at(data, uncomp_info_offset, num_entries * blocks * 8),
            big_endian=platform != PLATFORM_PC,
        )
        for entry in entries:
            for block in range(blocks):
                mapped = map_bndl_block_to_bnd2(platform, block)
                if mapped == -1:
                    info.skip(8)
                    continue
                entry.blocks[mapped].uncompressed_size = info.read_u32()
                entry.blocks[mapped].uncompressed_alignment = info.read_u32()
    rst_entry = next((entry for entry in entries if entry.resource_id == RST_RESOURCE_ID), None)
    if rst_entry is not None:
        flags |= FLAG_HAS_RST
        try:
            rst_payload = _read_block(data, rst_entry.blocks[0], compressed=bool(compressed))
            if len(rst_payload) >= 4:
                text_len = struct.unpack_from("<I", rst_payload, 0)[0]
                xml = rst_payload[4 : 4 + text_len].decode("utf-8", errors="replace")
                _apply_debug_info(entries, _parse_rst_xml(xml))
        except (BundleError, UnicodeError, struct.error):
            pass
    kept = [entry for entry in entries if entry.resource_id != RST_RESOURCE_ID]
    return BundleInfo(
        source=source,
        magic="BNDL",
        revision=revision,
        platform=platform,
        flags=flags,
        file_size=len(data),
        entries=kept,
        parsed_entries=len(kept),
        raw=data,
        big_endian=platform != PLATFORM_PC,
    )


def parse_bundle_bytes(data: bytes, source: str = "<memory>") -> BundleInfo:
    if len(data) < 4:
        raise BundleError("file is too small to be a BUNDLE archive")
    magic = data[:4]
    if magic == MAGIC_BND2:
        return parse_bnd2(data, source)
    if magic == MAGIC_BNDL:
        return parse_bndl(data, source)
    raise BundleError("not a BNDL/BND2 archive (need the 4-byte magic bndl or bnd2)")


def parse_bundle_path(path: Path) -> BundleInfo:
    size = path.stat().st_size
    if size < 4:
        raise BundleError("file is too small to be a BUNDLE archive")
    if size > MAX_FILE_BYTES:
        raise BundleError(f"file is larger than the {MAX_FILE_BYTES} byte cap")
    data = path.read_bytes()
    info = parse_bundle_bytes(data, str(path))
    info.file_size = size
    return info


def get_binary(info: BundleInfo, entry: ResourceEntry, file_block: int = 0) -> bytes:
    if file_block < 0 or file_block > 2:
        raise BundleError("file block must be 0, 1, or 2")
    return _read_block(info.raw, entry.blocks[file_block], compressed=bool(info.flags & FLAG_COMPRESSED))


def resolve_resource_type(token: str) -> int | None:
    raw = (token or "").strip()
    if not raw:
        return None
    if raw.lower() in TYPE_BY_NAME:
        return TYPE_BY_NAME[raw.lower()]
    if _RESOURCE_TOKEN.match(raw):
        return int(raw, 16)
    return None


def _overview_text() -> str:
    return (
        "libbndl is a C++ library for Criterion/EA BUNDLE archives used in "
        "Burnout Paradise and related titles (Black, and later BND2 games). "
        "It is consumed by libapt2.\n"
        "\n"
        f"This agent pins Bo98/libbndl @{PINNED_COMMIT[:7]} "
        f"({PINNED_COMMIT}).\n"
        "That commit adds non-Xbox BNDL (PC / PS3 as well as Xbox 360) and "
        "improves BNDL v3 and v4. BND2 remains revision 2. BNDL revisions "
        "3-5 are accepted.\n"
        "\n"
        "What this agent will do (pinned API):\n"
        "- Inspect / lookup / list-by-type on a local file or a fetched URL.\n"
        "- Extract GetBinary payloads (zlib-decompressed) to a local folder.\n"
        "- Create, add, and replace resources; Save writes BND2 PC.\n"
        "- Fetch an http(s) archive (size-capped, no private hosts).\n"
        "\n"
        "Writes always emit BND2 revision 2 for PC, matching libbndl's "
        "supported SaveBND2 path. BNDL sources are converted on save.\n"
        "\n"
        "Build the upstream library:\n"
        f"  {BUILD_COMMANDS}\n"
        "\n"
        f"Tree: {TREE_URL}\n"
        f"Commit: {COMMIT_URL}\n"
        f"libapt2: {LIBAPT2_URL}\n"
        "Local: python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl\n"
        "       python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl "
        "inspect <file>\n"
        "       python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl "
        "extract <file> <id-or-name> [outdir]\n"
        "       python3 BitcoinAgent/app/BitcoinAgent/local_cli.py libbndl "
        "create <out.bnd2> <name> <type> <payload>\n"
        "See BitcoinAgent/LIBBNDL.md."
    )


def _secret_query(text: str) -> bool:
    return reject_secrets(text) is not None


def _is_url(token: str) -> bool:
    return bool(re.match(r"^https?://", token or "", re.I))


def _host_is_public(host: str) -> bool:
    hostname = (host or "").split("%")[0]
    if not hostname or hostname.lower() in {"localhost", "metadata.google.internal"}:
        return False
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = info[4][0]
        try:
            parsed = ipaddress.ip_address(ip)
        except ValueError:
            return False
        if parsed.is_private or parsed.is_loopback or parsed.is_link_local or parsed.is_reserved:
            return False
    return True


def fetch_bundle_bytes(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise BundleError("only http and https URLs can be fetched")
    if parsed.username or parsed.password:
        raise BundleError("URLs with credentials are not fetched")
    if not _host_is_public(parsed.hostname or ""):
        raise BundleError("refusing to fetch a private or local host")
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "BitcoinAgent-libbndl/2b88eff"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            data = response.read(MAX_FETCH_BYTES + 1)
    except urllib.error.URLError as exc:
        raise BundleError(f"fetch failed: {exc}") from exc
    if len(data) > MAX_FETCH_BYTES:
        raise BundleError(f"download is larger than the {MAX_FETCH_BYTES} byte cap")
    if len(data) < 4:
        raise BundleError("downloaded file is too small to be a BUNDLE archive")
    return data


def _resolve_existing_file(raw: str) -> Path | str:
    token = (raw or "").strip()
    if not token:
        return "Provide a local BUNDLE path: libbndl inspect <file>"
    if _secret_query(token):
        return "Do not paste seed phrases, private keys, or wallet passwords."
    if _is_url(token):
        return token
    if re.match(r"^[a-z]+://", token, re.I):
        return "Only http(s) URLs or local files are accepted."
    path = Path(token).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        return f"Cannot resolve path: {exc}"
    if not path.exists():
        return f"File not found: {path}"
    if not path.is_file():
        return f"Not a file: {path}"
    return path


def _resolve_dest_path(raw: str, *, must_exist: bool = False) -> Path | str:
    token = (raw or "").strip()
    if not token:
        return "Provide a local destination path."
    if _secret_query(token):
        return "Do not paste seed phrases, private keys, or wallet passwords."
    if re.match(r"^[a-z]+://", token, re.I):
        return "Destination must be a local filesystem path."
    path = Path(token).expanduser()
    try:
        path = path.resolve()
    except OSError as exc:
        return f"Cannot resolve path: {exc}"
    if must_exist and not path.exists():
        return f"File not found: {path}"
    return path


def load_bundle(source: str) -> BundleInfo | str:
    resolved = _resolve_existing_file(source)
    if isinstance(resolved, str) and not _is_url(resolved):
        return resolved
    try:
        if isinstance(resolved, str) and _is_url(resolved):
            data = fetch_bundle_bytes(resolved)
            info = parse_bundle_bytes(data, resolved)
            info.file_size = len(data)
            return info
        return parse_bundle_path(resolved)
    except BundleError as exc:
        return f"Failed to load {resolved}: {exc}"
    except OSError as exc:
        return f"Cannot read {resolved}: {exc}"


def _format_header(info: BundleInfo) -> list[str]:
    return [
        f"libbndl inspect (Bo98/libbndl @{PINNED_COMMIT[:7]})",
        f"File: {info.source}",
        f"Size: {info.file_size} bytes",
        f"Format: {info.magic} revision {info.revision}",
        f"Platform: {platform_name(info.platform)}",
        f"Flags: {', '.join(flag_names(info.flags))}",
        f"Entries: {info.parsed_entries}",
    ]


def _format_entry_row(entry: ResourceEntry) -> str:
    sizes = "/".join(str(block.uncompressed_size) for block in entry.blocks)
    name = entry.name or "-"
    type_label = entry.type_name or resource_type_name(entry.resource_type)
    return f"0x{entry.resource_id:08X}  {type_label:<28} {name:<24} {sizes}"


def _format_bundle(info: BundleInfo, *, type_filter: int | None = None, limit: int = MAX_LIST_ENTRIES) -> str:
    entries = info.entries
    if type_filter is not None:
        entries = [entry for entry in entries if entry.resource_type == type_filter]
    lines = _format_header(info)
    if type_filter is not None:
        lines.append(f"Type filter: {resource_type_name(type_filter)} (0x{type_filter:X}) — {len(entries)} match(es)")
    if not entries:
        lines.append("No resources.")
        return "\n".join(lines)
    lines.append("")
    lines.append("ID          Type                         Name                     Uncomp blocks")
    shown = entries[:limit]
    lines.extend(_format_entry_row(entry) for entry in shown)
    leftover = len(entries) - len(shown)
    if leftover > 0:
        lines.append(f"... and {leftover} more. Use libbndl lookup <file> <id-or-name>.")
    return "\n".join(lines)


def _find_entry(info: BundleInfo, token: str) -> ResourceEntry | None:
    raw = token.strip()
    if not raw:
        return None
    if _RESOURCE_TOKEN.match(raw):
        resource_id = int(raw, 16)
        for entry in info.entries:
            if entry.resource_id == resource_id:
                return entry
    wanted = hash_resource_name(raw)
    for entry in info.entries:
        if entry.resource_id == wanted or entry.name.lower() == raw.lower():
            return entry
    return None


def _format_entry(info: BundleInfo, entry: ResourceEntry) -> str:
    lines = [
        f"libbndl lookup (Bo98/libbndl @{PINNED_COMMIT[:7]})",
        f"File: {info.source}",
        f"Resource: 0x{entry.resource_id:08X}",
    ]
    if entry.name:
        lines.append(f"Name: {entry.name}")
    lines.append(f"Type: {entry.type_name or resource_type_name(entry.resource_type)} (0x{entry.resource_type:X})")
    if entry.checksum:
        lines.append(f"Checksum: 0x{entry.checksum:08X}")
    lines.append(f"Dependencies: {entry.dependencies}")
    for index, block in enumerate(entry.blocks):
        lines.append(
            f"Block {index}: uncomp={block.uncompressed_size} "
            f"align={block.uncompressed_alignment} comp={block.compressed_size} "
            f"offset={block.data_offset}"
        )
    lines.append("Extract with: libbndl extract <file> <id-or-name> [outdir]")
    return "\n".join(lines)


def inspect_bundle(path: str, resource_type: str = "") -> str:
    info = load_bundle(path)
    if isinstance(info, str):
        return info
    type_filter = resolve_resource_type(resource_type) if resource_type else None
    if resource_type and type_filter is None:
        return f"Unknown resource type {resource_type!r}. Use a name such as TextFile or a hex ID."
    return _format_bundle(info, type_filter=type_filter)


def lookup_resource(path: str, resource: str) -> str:
    if _secret_query(f"{path} {resource}"):
        return "Do not paste seed phrases, private keys, or wallet passwords."
    info = load_bundle(path)
    if isinstance(info, str):
        return info
    token = (resource or "").strip()
    if not token:
        return "Provide a resource name or hex ID: libbndl lookup <file> <id-or-name>"
    entry = _find_entry(info, token)
    if entry is None:
        hashed = hash_resource_name(token)
        return (
            f"No resource {token!r} in {info.source} "
            f"(name hash 0x{hashed:08X}). {info.parsed_entries} entries parsed."
        )
    return _format_entry(info, entry)


def list_resource_ids_by_type(path: str) -> str:
    info = load_bundle(path)
    if isinstance(info, str):
        return info
    grouped: dict[int, list[ResourceEntry]] = {}
    for entry in info.entries:
        grouped.setdefault(entry.resource_type, []).append(entry)
    lines = [
        f"libbndl types (Bo98/libbndl @{PINNED_COMMIT[:7]})",
        f"File: {info.source}",
        f"Entries: {info.parsed_entries}",
        "",
    ]
    if not grouped:
        lines.append("No resources.")
        return "\n".join(lines)
    for resource_type in sorted(grouped):
        items = grouped[resource_type]
        lines.append(f"{resource_type_name(resource_type)} (0x{resource_type:X}): {len(items)}")
        for entry in items[:20]:
            label = entry.name or f"0x{entry.resource_id:08X}"
            lines.append(f"  {label}")
        if len(items) > 20:
            lines.append(f"  ... and {len(items) - 20} more")
    return "\n".join(lines)


def extract_resource(path: str, resource: str, outdir: str = "") -> str:
    if _secret_query(f"{path} {resource} {outdir}"):
        return "Do not paste seed phrases, private keys, or wallet passwords."
    info = load_bundle(path)
    if isinstance(info, str):
        return info
    token = (resource or "").strip()
    if not token:
        return "Provide a resource name or hex ID: libbndl extract <file> <id-or-name> [outdir]"
    entry = _find_entry(info, token)
    if entry is None:
        return f"No resource {token!r} in {info.source}."
    dest_raw = (outdir or "").strip()
    if dest_raw:
        dest = _resolve_dest_path(dest_raw)
        if isinstance(dest, str):
            return dest
    else:
        stem = Path(urlparse(info.source).path).stem or "bundle"
        dest = Path.cwd() / f"{stem}-extract"
    dest.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for index in range(3):
        try:
            payload = get_binary(info, entry, index)
        except BundleError as exc:
            return f"Failed to extract block {index}: {exc}"
        if not payload:
            continue
        name = entry.name or f"{entry.resource_id:08x}"
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
        out_path = dest / f"{safe}.block{index}"
        out_path.write_bytes(payload)
        written.append(f"{out_path} ({len(payload)} bytes)")
    if not written:
        return f"Resource 0x{entry.resource_id:08X} has no payload bytes in any file block."
    return "Extracted:\n" + "\n".join(f"  {line}" for line in written)


def _align_buf(buf: bytearray, alignment: int) -> None:
    if alignment <= 1:
        return
    pad = (-len(buf)) % alignment
    buf.extend(b"\x00" * pad)


def _alignment_nibble(alignment: int) -> int:
    if alignment <= 1:
        return 0
    return alignment.bit_length() - 1


def save_bnd2_pc(entries: list[ResourceEntry], payloads: dict[int, list[bytes]]) -> bytes:
    flags = FLAG_UNUSED1 | FLAG_UNUSED2
    if any(entry.name for entry in entries):
        flags |= FLAG_HAS_RST
    out = bytearray()
    out.extend(MAGIC_BND2)
    out.extend(struct.pack("<I", 2))
    out.extend(struct.pack("<I", PLATFORM_PC))
    rst_ptr = len(out)
    out.extend(b"\x00" * 4)
    out.extend(struct.pack("<I", len(entries)))
    id_ptr = len(out)
    out.extend(b"\x00" * 4)
    block_ptrs = []
    for _ in range(3):
        block_ptrs.append(len(out))
        out.extend(b"\x00" * 4)
    out.extend(struct.pack("<I", flags))
    out.extend(b"\x00" * 8)
    _align_buf(out, 16)
    struct.pack_into("<I", out, rst_ptr, len(out))
    if flags & FLAG_HAS_RST:
        lines = ['<ResourceStringTable>']
        for entry in entries:
            type_label = entry.type_name or resource_type_name(entry.resource_type)
            name = entry.name or f"{entry.resource_id:08x}"
            lines.append(
                f'<Resource id="{entry.resource_id:08x}" type="{type_label}" name="{name}"/>'
            )
        lines.append("</ResourceStringTable>")
        out.extend("\n".join(lines).encode("utf-8") + b"\x00")
        _align_buf(out, 16)
    struct.pack_into("<I", out, id_ptr, len(out))
    rel_slots: list[list[int]] = []
    for entry in entries:
        out.extend(struct.pack("<Q", entry.resource_id))
        out.extend(struct.pack("<Q", entry.checksum))
        blocks_payload = payloads.get(entry.resource_id, [b"", b"", b""])
        for index in range(3):
            payload = blocks_payload[index] if index < len(blocks_payload) else b""
            align = entry.blocks[index].uncompressed_alignment or 1
            packed = len(payload) | (_alignment_nibble(align) << 28)
            out.extend(struct.pack("<I", packed))
        for _ in range(3):
            out.extend(struct.pack("<I", 0))
        slots = []
        for _ in range(3):
            slots.append(len(out))
            out.extend(b"\x00" * 4)
        rel_slots.append(slots)
        out.extend(struct.pack("<I", 0))
        out.extend(struct.pack("<I", entry.resource_type))
        out.extend(struct.pack("<H", entry.dependencies))
        out.extend(struct.pack("<H", 0))
    for block_index in range(3):
        block_start = len(out)
        struct.pack_into("<I", out, block_ptrs[block_index], block_start)
        for entry_index, entry in enumerate(entries):
            blocks_payload = payloads.get(entry.resource_id, [b"", b"", b""])
            payload = blocks_payload[block_index] if block_index < len(blocks_payload) else b""
            if not payload:
                continue
            struct.pack_into("<I", out, rel_slots[entry_index][block_index], len(out) - block_start)
            out.extend(payload)
            last = entry_index == len(entries) - 1
            _align_buf(out, 16 if (block_index == 0 or last) else 0x80)
        if block_index != 2:
            _align_buf(out, 0x80)
    return bytes(out)


def _entry_payloads(info: BundleInfo) -> dict[int, list[bytes]]:
    out: dict[int, list[bytes]] = {}
    for entry in info.entries:
        blocks = []
        for index in range(3):
            try:
                blocks.append(get_binary(info, entry, index))
            except BundleError:
                blocks.append(b"")
        out[entry.resource_id] = blocks
    return out


def _write_bundle(path: Path, entries: list[ResourceEntry], payloads: dict[int, list[bytes]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = save_bnd2_pc(entries, payloads)
    path.write_bytes(data)
    return f"Wrote BND2 PC archive {path} ({len(data)} bytes, {len(entries)} resource(s))."


def create_bundle(out_path: str, name: str, resource_type: str, payload_path: str) -> str:
    dest = _resolve_dest_path(out_path)
    if isinstance(dest, str):
        return dest
    payload_file = _resolve_dest_path(payload_path, must_exist=True)
    if isinstance(payload_file, str):
        return payload_file
    if not payload_file.is_file():
        return f"Not a file: {payload_file}"
    type_id = resolve_resource_type(resource_type)
    if type_id is None:
        return f"Unknown resource type {resource_type!r}."
    data = payload_file.read_bytes()
    if len(data) > MAX_PAYLOAD_BYTES:
        return f"Payload is larger than the {MAX_PAYLOAD_BYTES} byte cap."
    resource_name = (name or payload_file.name).strip()
    entry = ResourceEntry(
        resource_id=hash_resource_name(resource_name),
        resource_type=type_id,
        name=resource_name,
        type_name=resource_type_name(type_id),
        blocks=[BlockInfo(uncompressed_alignment=4), BlockInfo(), BlockInfo()],
    )
    return _write_bundle(dest, [entry], {entry.resource_id: [data, b"", b""]})


def add_resource(archive: str, name: str, resource_type: str, payload_path: str, out_path: str = "") -> str:
    info = load_bundle(archive)
    if isinstance(info, str):
        return info
    target = out_path or ("" if _is_url(info.source) else info.source)
    dest = _resolve_dest_path(target)
    if isinstance(dest, str):
        if not out_path and _is_url(info.source):
            return "Provide a local destination: libbndl add <url> <name> <type> <payload> <out.bnd2>"
        return dest
    payload_file = _resolve_dest_path(payload_path, must_exist=True)
    if isinstance(payload_file, str):
        return payload_file
    type_id = resolve_resource_type(resource_type)
    if type_id is None:
        return f"Unknown resource type {resource_type!r}."
    resource_name = (name or payload_file.name).strip()
    resource_id = hash_resource_name(resource_name)
    if any(entry.resource_id == resource_id for entry in info.entries):
        return f"Resource {resource_name!r} (0x{resource_id:08X}) already exists. Use replace."
    data = payload_file.read_bytes()
    if len(data) > MAX_PAYLOAD_BYTES:
        return f"Payload is larger than the {MAX_PAYLOAD_BYTES} byte cap."
    payloads = _entry_payloads(info)
    entry = ResourceEntry(
        resource_id=resource_id,
        resource_type=type_id,
        name=resource_name,
        type_name=resource_type_name(type_id),
        blocks=[BlockInfo(uncompressed_alignment=4), BlockInfo(), BlockInfo()],
    )
    payloads[resource_id] = [data, b"", b""]
    return _write_bundle(dest, [*info.entries, entry], payloads)


def replace_resource(archive: str, resource: str, payload_path: str, out_path: str = "") -> str:
    info = load_bundle(archive)
    if isinstance(info, str):
        return info
    dest = _resolve_dest_path(out_path or ("" if _is_url(info.source) else info.source))
    if isinstance(dest, str):
        if not out_path and _is_url(info.source):
            return "Provide a local destination: libbndl replace <url> <id> <payload> <out.bnd2>"
        return dest
    payload_file = _resolve_dest_path(payload_path, must_exist=True)
    if isinstance(payload_file, str):
        return payload_file
    entry = _find_entry(info, resource)
    if entry is None:
        return f"No resource {resource!r} in {info.source}."
    data = payload_file.read_bytes()
    if len(data) > MAX_PAYLOAD_BYTES:
        return f"Payload is larger than the {MAX_PAYLOAD_BYTES} byte cap."
    payloads = _entry_payloads(info)
    payloads[entry.resource_id] = [data, b"", b""]
    return _write_bundle(dest, info.entries, payloads)


def fetch_archive(url: str, dest_path: str = "") -> str:
    if _secret_query(f"{url} {dest_path}"):
        return "Do not paste seed phrases, private keys, or wallet passwords."
    token = (url or "").strip()
    if not _is_url(token):
        return "Provide an http(s) URL: libbndl fetch <url> [dest]"
    try:
        data = fetch_bundle_bytes(token)
    except BundleError as exc:
        return f"Fetch failed: {exc}"
    dest: Path
    if dest_path.strip():
        resolved = _resolve_dest_path(dest_path)
        if isinstance(resolved, str):
            return resolved
        dest = resolved
    else:
        name = Path(urlparse(token).path).name or "downloaded.BNDL"
        dest = Path.cwd() / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    try:
        info = parse_bundle_bytes(data, str(dest))
    except BundleError as exc:
        return f"Saved {dest} ({len(data)} bytes) but it is not a BUNDLE archive: {exc}"
    return f"Fetched {token} -> {dest} ({len(data)} bytes)\n{_format_bundle(info)}"


@tool
def libbndl_overview() -> str:
    """Explain libbndl at the pinned 2b88eff commit (inspect, extract, save, fetch)."""
    return _overview_text()


@tool
def libbndl_inspect(path: str, resource_type: str = "") -> str:
    """Inspect a BNDL/BND2 archive: platform, revision, flags, resources.

    Path is a local file or http(s) URL. Optional resource_type filters the list
    (TextFile, Raster, or a hex type ID). Pinned to Bo98/libbndl@2b88eff.
    """
    return inspect_bundle(path, resource_type)


@tool
def libbndl_lookup(path: str, resource: str) -> str:
    """Look up one resource in a BNDL/BND2 file by name or hex ID.

    Names are hashed with CRC-32 of the lowercased string, matching libbndl.
    """
    return lookup_resource(path, resource)


@tool
def libbndl_types(path: str) -> str:
    """List resource IDs grouped by type (ListResourceIDsByType)."""
    return list_resource_ids_by_type(path)


@tool
def libbndl_extract(path: str, resource: str, outdir: str = "") -> str:
    """Extract GetBinary payloads for one resource to a local folder.

    Writes <name>.block0/1/2 after zlib decompress when the archive is
    compressed. Does not execute extracted data.
    """
    return extract_resource(path, resource, outdir)


@tool
def libbndl_create(out_path: str, name: str, resource_type: str, payload_path: str) -> str:
    """Create a new BND2 PC archive with one resource (Save / AddResource)."""
    return create_bundle(out_path, name, resource_type, payload_path)


@tool
def libbndl_add(archive: str, name: str, resource_type: str, payload_path: str, out_path: str = "") -> str:
    """Add a resource to an archive and Save as BND2 PC."""
    return add_resource(archive, name, resource_type, payload_path, out_path)


@tool
def libbndl_replace(archive: str, resource: str, payload_path: str, out_path: str = "") -> str:
    """Replace one resource payload and Save as BND2 PC."""
    return replace_resource(archive, resource, payload_path, out_path)


@tool
def libbndl_fetch(url: str, dest_path: str = "") -> str:
    """Download an http(s) BUNDLE archive, save it locally, and inspect it."""
    return fetch_archive(url, dest_path)


def libbndl_from_arg(text: str) -> str:
    """Route a local-CLI argument string onto the full libbndl tool set."""
    raw = (text or "").strip()
    lower = raw.lower()
    if not raw or lower in {"overview", "help", "docs"}:
        return libbndl_overview()
    fetch_match = re.match(r"^fetch\b(?:\s+(\S+))?(?:\s+(\S+))?$", raw, re.I)
    if fetch_match:
        return libbndl_fetch(fetch_match.group(1) or "", fetch_match.group(2) or "")
    types_match = re.match(r"^(types|by-type|bytype)\b(?:\s+(.*))?$", raw, re.I)
    if types_match:
        return libbndl_types(types_match.group(2) or "")
    extract_match = re.match(r"^(extract|getbinary|dump)\b(?:\s+(\S+))(?:\s+(\S+))?(?:\s+(\S+))?$", raw, re.I)
    if extract_match:
        return libbndl_extract(extract_match.group(2), extract_match.group(3) or "", extract_match.group(4) or "")
    create_match = re.match(
        r"^create\b(?:\s+(\S+))(?:\s+(\S+))(?:\s+(\S+))(?:\s+(\S+))?$",
        raw,
        re.I,
    )
    if create_match:
        return libbndl_create(
            create_match.group(1),
            create_match.group(2),
            create_match.group(3),
            create_match.group(4) or "",
        )
    add_match = re.match(
        r"^add\b(?:\s+(\S+))(?:\s+(\S+))(?:\s+(\S+))(?:\s+(\S+))?(?:\s+(\S+))?$",
        raw,
        re.I,
    )
    if add_match:
        return libbndl_add(
            add_match.group(1),
            add_match.group(2),
            add_match.group(3),
            add_match.group(4) or "",
            add_match.group(5) or "",
        )
    replace_match = re.match(
        r"^replace\b(?:\s+(\S+))(?:\s+(\S+))(?:\s+(\S+))?(?:\s+(\S+))?$",
        raw,
        re.I,
    )
    if replace_match:
        return libbndl_replace(
            replace_match.group(1),
            replace_match.group(2),
            replace_match.group(3) or "",
            replace_match.group(4) or "",
        )
    inspect_match = re.match(r"^(inspect|info|list|open|read|show)\b(?:\s+(.*))?$", raw, re.I)
    if inspect_match:
        rest = inspect_match.group(2) or ""
        type_match = re.match(r"^(\S+)\s+type\s+(\S+)$", rest, re.I)
        if type_match:
            return libbndl_inspect(type_match.group(1), type_match.group(2))
        return libbndl_inspect(rest)
    lookup_match = re.match(r"^(lookup|get|find|resource)\b(?:\s+(\S+))(?:\s+(.*))?$", raw, re.I)
    if lookup_match and lookup_match.group(3):
        return libbndl_lookup(lookup_match.group(2), lookup_match.group(3))
    if lookup_match:
        return libbndl_inspect(lookup_match.group(2) or "")
    if _is_url(raw.split()[0] if raw else ""):
        parts = raw.split()
        if len(parts) >= 2 and parts[1].lower() == "fetch":
            return libbndl_fetch(parts[0], parts[2] if len(parts) > 2 else "")
        return libbndl_inspect(parts[0])
    tokens = [token for token in _PATH_TOKEN.findall(raw) if token.lower() not in _STOPWORDS]
    if len(tokens) >= 2 and Path(tokens[0]).suffix.lower() in {".bndl", ".bnd2", ".bundle"}:
        return libbndl_lookup(tokens[0], tokens[1])
    if len(tokens) >= 2 and Path(tokens[-2]).suffix.lower() in {".bndl", ".bnd2", ".bundle"}:
        return libbndl_lookup(tokens[-2], tokens[-1])
    if tokens:
        return libbndl_inspect(tokens[0])
    return libbndl_overview()
