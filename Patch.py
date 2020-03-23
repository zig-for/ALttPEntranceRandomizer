import bsdiff4
import yaml
import os
import lzma
import hashlib
from typing import Tuple

import Utils
from Rom import JAP10HASH, read_rom

base_rom_bytes = None


def get_base_rom_bytes() -> bytes:
    global base_rom_bytes
    if not base_rom_bytes:
        options = Utils.get_options()
        file_name = options["general_options"]["rom_file"]
        if not os.path.exists(file_name):
            file_name = Utils.local_path(file_name)
        base_rom_bytes = bytes(read_rom(open(file_name, "rb")))

        basemd5 = hashlib.md5()
        basemd5.update(base_rom_bytes)
        if JAP10HASH != basemd5.hexdigest():
            raise Exception('Supplied Base Rom does not match known MD5 for JAP(1.0) release. '
                            'Get the correct game and version, then dump it')
    return base_rom_bytes


def generate_patch(rom: bytes, metadata=None) -> bytes:
    if metadata is None:
        metadata = {}
    patch = bsdiff4.diff(get_base_rom_bytes(), rom)
    patch = yaml.dump({"meta": metadata,
                       "patch": patch})
    return patch.encode(encoding="utf-8-sig")


def create_patch_file(rom_file_to_patch: str, server: str = "") -> str:
    bytes = generate_patch(load_bytes(rom_file_to_patch),
                           {
                               "server": server})  # allow immediate connection to server in multiworld. Empty string otherwise
    target = os.path.splitext(rom_file_to_patch)[0] + ".bmbp"
    write_lzma(bytes, target)
    return target


def create_rom_file(patch_file) -> Tuple[dict, str]:
    data = Utils.parse_yaml(lzma.decompress(load_bytes(patch_file)).decode("utf-8-sig"))
    patched_data = bsdiff4.patch(get_base_rom_bytes(), data["patch"])
    target = os.path.splitext(patch_file)[0] + ".sfc"
    with open(target, "wb") as f:
        f.write(patched_data)
    return data["meta"], target


def load_bytes(path: str):
    with open(path, "rb") as f:
        return f.read()


def write_lzma(data: bytes, path: str):
    with lzma.LZMAFile(path, 'wb') as f:
        f.write(data)

if __name__ == "__main__":
    ipv4 = Utils.get_public_ipv4()
    import sys

    for rom in sys.argv:
        if rom.endswith(".sfc"):
            print(f"Creating patch for {rom}")
            result = create_patch_file(rom, ipv4)
            print(f"Created patch {result}")
