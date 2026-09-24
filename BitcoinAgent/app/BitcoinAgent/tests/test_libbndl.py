from __future__ import annotations

import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from bitcoin_tools import developer_howto
from libbndl import (
    COMMIT_URL,
    FLAG_HAS_RST,
    MAGIC_BND2,
    MAGIC_BNDL,
    PINNED_COMMIT,
    PLATFORM_PC,
    PLATFORM_PS3,
    PLATFORM_XBOX360,
    TREE_URL,
    BundleError,
    fetch_bundle_bytes,
    get_binary,
    hash_resource_name,
    libbndl_add,
    libbndl_create,
    libbndl_extract,
    libbndl_fetch,
    libbndl_from_arg,
    libbndl_inspect,
    libbndl_lookup,
    libbndl_overview,
    libbndl_replace,
    libbndl_types,
    map_bndl_block_to_bnd2,
    parse_bundle_bytes,
    parse_bundle_path,
    platform_name,
)
from local_cli import route_query

REPO_ROOT = Path(__file__).resolve().parents[4]
OVERVIEW_DOC = REPO_ROOT / "BitcoinAgent" / "LIBBNDL.md"


def _u32(value: int, big_endian: bool = False) -> bytes:
    return struct.pack(">I" if big_endian else "<I", value)


def _u16(value: int, big_endian: bool = False) -> bytes:
    return struct.pack(">H" if big_endian else "<H", value)


def _u64(value: int, big_endian: bool = False) -> bytes:
    return struct.pack(">Q" if big_endian else "<Q", value)


def build_bnd2_pc(
    *,
    resource_id: int = 0x12345678,
    resource_type: int = 0x03,
    name: str = "hello.txt",
    payload: bytes = b"hello!",
    compressed: bool = False,
) -> bytes:
    stored = zlib.compress(payload) if compressed else payload
    rst = (
        '<?xml version="1.0"?>\n'
        "<ResourceStringTable>\n"
        f'  <Resource id="{resource_id:08x}" type="TextFile" name="{name}"/>\n'
        "</ResourceStringTable>\n"
    ).encode("utf-8") + b"\x00"
    header_size = 0x30
    id_offset = header_size
    data_offset = id_offset + 64
    rst_offset = data_offset + len(stored)
    packed = len(payload)  # alignment nibble 0 -> align 1
    flags = FLAG_HAS_RST | (1 if compressed else 0)
    entry = b"".join(
        [
            _u64(resource_id),
            _u64(0),
            _u32(packed),
            _u32(0),
            _u32(0),
            _u32(len(stored) if compressed else 0),
            _u32(0),
            _u32(0),
            _u32(0),
            _u32(0),
            _u32(0),
            _u32(0),
            _u32(resource_type),
            _u16(0),
            _u16(0),
        ]
    )
    header = b"".join(
        [
            MAGIC_BND2,
            _u32(2),
            _u32(PLATFORM_PC),
            _u32(rst_offset),
            _u32(1),
            _u32(id_offset),
            _u32(data_offset),
            _u32(0),
            _u32(0),
            _u32(flags),
            b"\x00" * 8,
        ]
    )
    return header + entry + stored + rst


def build_bndl_v3(platform: int, *, resource_id: int = 0x11111111, resource_type: int = 0x03) -> bytes:
    big = platform != PLATFORM_PC
    if platform == PLATFORM_XBOX360:
        blocks = 5
        platform_off = 0x58
    elif platform == PLATFORM_PS3:
        blocks = 6
        platform_off = 0x64
    else:
        blocks = 4
        platform_off = 0x4C
    header = bytearray(platform_off + 4)
    header[0:4] = MAGIC_BNDL
    header[4:8] = _u32(3, big)
    header[8:12] = _u32(1, big)
    cursor = 12
    for _ in range(blocks):
        header[cursor : cursor + 4] = _u32(0, big)
        header[cursor + 4 : cursor + 8] = _u32(1, big)
        cursor += 8
    cursor += 4 * blocks  # memory addresses
    id_list_off = platform_off + 4
    id_table_off = id_list_off + 8
    header[cursor : cursor + 4] = _u32(id_list_off, big)
    header[cursor + 4 : cursor + 8] = _u32(id_table_off, big)
    header[cursor + 8 : cursor + 12] = _u32(0, big)
    header[cursor + 12 : cursor + 16] = _u32(0, big)
    header[platform_off : platform_off + 4] = _u32(platform, False)
    id_list = _u64(resource_id, big)
    table = bytearray()
    table += _u32(0, big)
    table += _u32(0, big)
    table += _u32(resource_type, big)
    for block in range(blocks):
        mapped = map_bndl_block_to_bnd2(platform, block)
        if mapped == -1:
            table += _u32(0, big) + _u32(1, big)
        elif mapped == 0:
            table += _u32(32, big) + _u32(4, big)
        else:
            table += _u32(0, big) + _u32(1, big)
    payload = b"P" * 32
    payload_offset = platform_off + 4 + 8 + len(table) + (8 * blocks) + (4 * blocks)
    for block in range(blocks):
        mapped = map_bndl_block_to_bnd2(platform, block)
        if mapped == 0:
            table += _u32(payload_offset, big) + _u32(1, big)
        else:
            table += _u32(0, big) + _u32(1, big)
    table += b"\x00" * (4 * blocks)
    return bytes(header) + id_list + bytes(table) + payload


class LibbndlOverviewTests(unittest.TestCase):
    def test_overview_pins_commit_and_covers_full_api(self) -> None:
        text = libbndl_overview()
        lowered = text.lower()
        self.assertIn(PINNED_COMMIT, text)
        self.assertIn(TREE_URL, text)
        self.assertIn(COMMIT_URL, text)
        self.assertIn("non-xbox", lowered)
        self.assertIn("extract", lowered)
        self.assertIn("create", lowered)
        self.assertIn("fetch", lowered)
        self.assertIn("cmake", lowered)

    def test_repo_overview_doc_exists(self) -> None:
        self.assertTrue(OVERVIEW_DOC.is_file())
        body = OVERVIEW_DOC.read_text(encoding="utf-8")
        self.assertIn(PINNED_COMMIT, body)
        self.assertIn("non-Xbox", body)
        self.assertIn("libbndl inspect", body)

    def test_howto_libbndl_topic(self) -> None:
        text = developer_howto("libbndl")
        self.assertIn(PINNED_COMMIT[:7], text)
        self.assertIn("inspect", text)
        self.assertEqual(developer_howto("bndl"), text)
        self.assertEqual(developer_howto("bundle"), text)


class LibbndlParseTests(unittest.TestCase):
    def test_hash_resource_name_matches_crc32_lower(self) -> None:
        self.assertEqual(hash_resource_name("Hello.TXT"), zlib.crc32(b"hello.txt") & 0xFFFFFFFF)

    def test_map_bndl_blocks_match_pinned_cpp(self) -> None:
        self.assertEqual([map_bndl_block_to_bnd2(PLATFORM_PC, i) for i in range(4)], [0, 1, 2, -1])
        self.assertEqual(
            [map_bndl_block_to_bnd2(PLATFORM_XBOX360, i) for i in range(5)],
            [0, -1, 1, 2, -1],
        )
        self.assertEqual(
            [map_bndl_block_to_bnd2(PLATFORM_PS3, i) for i in range(6)],
            [0, -1, -1, -1, 1, 2],
        )

    def test_parse_bnd2_pc_with_rst(self) -> None:
        blob = build_bnd2_pc()
        info = parse_bundle_bytes(blob, "mem.bnd2")
        self.assertEqual(info.magic, "BND2")
        self.assertEqual(info.revision, 2)
        self.assertEqual(info.platform, PLATFORM_PC)
        self.assertEqual(len(info.entries), 1)
        entry = info.entries[0]
        self.assertEqual(entry.resource_id, 0x12345678)
        self.assertEqual(entry.name, "hello.txt")
        self.assertEqual(entry.type_name, "TextFile")
        self.assertEqual(entry.blocks[0].uncompressed_size, 6)

    def test_parse_bndl_v3_pc_is_the_non_xbox_path(self) -> None:
        blob = build_bndl_v3(PLATFORM_PC)
        info = parse_bundle_bytes(blob, "pc.bndl")
        self.assertEqual(info.magic, "BNDL")
        self.assertEqual(info.revision, 3)
        self.assertEqual(platform_name(info.platform), "PC (or PS4/XB1)")
        self.assertEqual(info.entries[0].resource_id, 0x11111111)
        self.assertEqual(info.entries[0].blocks[0].uncompressed_size, 32)

    def test_parse_bndl_v3_xbox_and_ps3(self) -> None:
        xbox = parse_bundle_bytes(build_bndl_v3(PLATFORM_XBOX360), "x.bndl")
        ps3 = parse_bundle_bytes(build_bndl_v3(PLATFORM_PS3), "p.bndl")
        self.assertEqual(xbox.platform, PLATFORM_XBOX360)
        self.assertEqual(ps3.platform, PLATFORM_PS3)
        self.assertEqual(xbox.entries[0].blocks[0].uncompressed_size, 32)
        self.assertEqual(ps3.entries[0].blocks[0].uncompressed_size, 32)

    def test_reject_bad_magic(self) -> None:
        with self.assertRaises(BundleError):
            parse_bundle_bytes(b"PK\x03\x04not-a-bundle")

    def test_inspect_and_lookup_round_trip(self) -> None:
        blob = build_bnd2_pc(name="world.txt")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "world.BND2"
            path.write_bytes(blob)
            listed = libbndl_inspect(str(path))
            self.assertIn("BND2 revision 2", listed)
            self.assertIn("world.txt", listed)
            self.assertIn("0x12345678", listed)
            by_id = libbndl_lookup(str(path), "0x12345678")
            self.assertIn("TextFile", by_id)
            by_name = libbndl_lookup(str(path), "world.txt")
            self.assertIn("0x12345678", by_name)
            missing = libbndl_lookup(str(path), "nope")
            self.assertIn("No resource", missing)

    def test_inspect_missing_and_rejects_secrets(self) -> None:
        self.assertIn("File not found", libbndl_inspect("/no/such/bundle.BNDL"))
        self.assertIn("seed", libbndl_inspect("my seed phrase apple").lower())

    def test_extract_uncompressed_and_compressed(self) -> None:
        plain = build_bnd2_pc(payload=b"hello!")
        zipped = build_bnd2_pc(payload=b"hello!", compressed=True)
        info = parse_bundle_bytes(plain, "plain.bnd2")
        self.assertEqual(get_binary(info, info.entries[0], 0), b"hello!")
        zinfo = parse_bundle_bytes(zipped, "zip.bnd2")
        self.assertEqual(get_binary(zinfo, zinfo.entries[0], 0), b"hello!")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.BND2"
            path.write_bytes(plain)
            out = Path(tmp) / "out"
            text = libbndl_extract(str(path), "hello.txt", str(out))
            self.assertIn("Extracted", text)
            self.assertEqual((out / "hello.txt.block0").read_bytes(), b"hello!")

    def test_create_add_replace_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "note.txt"
            payload.write_text("first", encoding="utf-8")
            extra = Path(tmp) / "extra.txt"
            extra.write_text("second", encoding="utf-8")
            archive = Path(tmp) / "pack.bnd2"
            created = libbndl_create(str(archive), "note.txt", "TextFile", str(payload))
            self.assertIn("Wrote BND2", created)
            listed = libbndl_inspect(str(archive))
            self.assertIn("note.txt", listed)
            self.assertIn("TextFile", libbndl_types(str(archive)))
            added = libbndl_add(str(archive), "extra.txt", "RawFile", str(extra))
            self.assertIn("2 resource", added)
            replaced_payload = Path(tmp) / "note2.txt"
            replaced_payload.write_text("third", encoding="utf-8")
            libbndl_replace(str(archive), "note.txt", str(replaced_payload))
            out = Path(tmp) / "extracted"
            libbndl_extract(str(archive), "note.txt", str(out))
            self.assertEqual((out / "note.txt.block0").read_bytes(), b"third")

    def test_fetch_saves_and_inspects(self) -> None:
        blob = build_bnd2_pc()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "remote.bnd2"
            with patch("libbndl.fetch_bundle_bytes", return_value=blob):
                text = libbndl_fetch("https://example.com/cars.BND2", str(dest))
            self.assertIn("Fetched", text)
            self.assertIn("hello.txt", text)
            self.assertTrue(dest.is_file())
            self.assertEqual(dest.read_bytes()[:4], MAGIC_BND2)

    def test_fetch_rejects_private_hosts(self) -> None:
        with self.assertRaises(BundleError):
            fetch_bundle_bytes("https://127.0.0.1/secret.BNDL")
        with self.assertRaises(BundleError):
            fetch_bundle_bytes("file:///etc/passwd")

    def test_parse_path_uses_disk_bytes(self) -> None:
        blob = build_bndl_v3(PLATFORM_PC)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cars.BNDL"
            path.write_bytes(blob)
            info = parse_bundle_path(path)
            self.assertEqual(info.file_size, len(blob))
            self.assertEqual(info.magic, "BNDL")


class LibbndlCliTests(unittest.TestCase):
    def test_local_cli_routes_overview(self) -> None:
        text = route_query("what is libbndl")
        self.assertIn(PINNED_COMMIT, text)
        self.assertIn("BUNDLE", text)

    def test_local_cli_inspects_fixture(self) -> None:
        blob = build_bnd2_pc()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bnd2"
            path.write_bytes(blob)
            text = route_query(f"libbndl inspect {path}")
            self.assertIn("hello.txt", text)
            lookup = route_query(f"libbndl lookup {path} hello.txt")
            self.assertIn("0x12345678", lookup)

    def test_from_arg_defaults_to_overview(self) -> None:
        self.assertIn(PINNED_COMMIT, libbndl_from_arg(""))
        self.assertIn(PINNED_COMMIT, libbndl_from_arg("docs"))

    def test_help_lists_libbndl(self) -> None:
        text = route_query("help")
        self.assertIn("libbndl", text)

    def test_howto_route(self) -> None:
        text = route_query("howto libbndl")
        self.assertIn("inspect", text)
        self.assertIn("extract", text)
        self.assertIn(PINNED_COMMIT[:7], text)

    def test_local_cli_create_and_extract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "hello.txt"
            payload.write_bytes(b"hello!")
            archive = Path(tmp) / "out.bnd2"
            created = route_query(f"libbndl create {archive} hello.txt TextFile {payload}")
            self.assertIn("Wrote BND2", created)
            extracted = route_query(f"libbndl extract {archive} hello.txt {tmp}/x")
            self.assertIn("Extracted", extracted)


if __name__ == "__main__":
    unittest.main()
