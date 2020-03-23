import os
import re
import subprocess
import sys
import typing
import functools

from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


def int16_as_bytes(value):
    value = value & 0xFFFF
    return [value & 0xFF, (value >> 8) & 0xFF]


def int32_as_bytes(value):
    value = value & 0xFFFFFFFF
    return [value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF]


def pc_to_snes(value):
    return ((value<<1) & 0x7F0000)|(value & 0x7FFF)|0x8000

def snes_to_pc(value):
    return ((value & 0x7F0000)>>1)|(value & 0x7FFF)

def parse_player_names(names, players, teams):
    names = tuple(n for n in (n.strip() for n in names.split(",")) if n)
    ret = []
    while names or len(ret) < teams:
        team = [n[:16] for n in names[:players]]
        # where does the 16 character limit come from?
        while len(team) != players:
            team.append(f"Player {len(team) + 1}")
        ret.append(team)

        names = names[players:]
    return ret

def is_bundled():
    return getattr(sys, 'frozen', False)

def local_path(path):
    if local_path.cached_path:
        return os.path.join(local_path.cached_path, path)

    elif is_bundled() and hasattr(sys, "_MEIPASS"):
        # we are running in a PyInstaller bundle
        local_path.cached_path = sys._MEIPASS  # pylint: disable=protected-access,no-member

    else:
        # we are running in a normal Python environment
        # or cx_Freeze
        local_path.cached_path = os.path.dirname(os.path.abspath(sys.argv[0]))

    return os.path.join(local_path.cached_path, path)

local_path.cached_path = None

def output_path(path):
    if output_path.cached_path:
        return os.path.join(output_path.cached_path, path)

    if not is_bundled() and not hasattr(sys, "_MEIPASS"):
        # this should trigger if it's cx_freeze bundling
        output_path.cached_path = '.'
        return os.path.join(output_path.cached_path, path)
    else:
        # has been PyInstaller packaged, so cannot use CWD for output.
        if sys.platform == 'win32':
            # windows
            import ctypes.wintypes
            CSIDL_PERSONAL = 5  # My Documents
            SHGFP_TYPE_CURRENT = 0  # Get current, not default value

            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)

            documents = buf.value

        elif sys.platform == 'darwin':
            from AppKit import NSSearchPathForDirectoriesInDomains # pylint: disable=import-error
            # http://developer.apple.com/DOCUMENTATION/Cocoa/Reference/Foundation/Miscellaneous/Foundation_Functions/Reference/reference.html#//apple_ref/c/func/NSSearchPathForDirectoriesInDomains
            NSDocumentDirectory = 9
            NSUserDomainMask = 1
            # True for expanding the tilde into a fully qualified path
            documents = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, True)[0]
        else:
            raise NotImplementedError('Not supported yet')

        output_path.cached_path = os.path.join(documents, 'ALttPEntranceRandomizer')
        if not os.path.exists(output_path.cached_path):
            os.mkdir(output_path.cached_path)
        return os.path.join(output_path.cached_path, path)

output_path.cached_path = None

def open_file(filename):
    if sys.platform == 'win32':
        os.startfile(filename)
    else:
        open_command = 'open' if sys.platform == 'darwin' else 'xdg-open'
        subprocess.call([open_command, filename])

def close_console():
    if sys.platform == 'win32':
        #windows
        import ctypes.wintypes
        try:
            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass

def make_new_base2current(old_rom='Zelda no Densetsu - Kamigami no Triforce (Japan).sfc', new_rom='working.sfc'):
    from collections import OrderedDict
    import json
    import hashlib
    with open(old_rom, 'rb') as stream:
        old_rom_data = bytearray(stream.read())
    with open(new_rom, 'rb') as stream:
        new_rom_data = bytearray(stream.read())
    # extend to 2 mb
    old_rom_data.extend(bytearray([0x00]) * (2097152 - len(old_rom_data)))

    out_data = OrderedDict()
    for idx, old in enumerate(old_rom_data):
        new = new_rom_data[idx]
        if old != new:
            out_data[idx] = [int(new)]
    for offset in reversed(list(out_data.keys())):
        if offset - 1 in out_data:
            out_data[offset-1].extend(out_data.pop(offset))
    with open('data/base2current.json', 'wt') as outfile:
        json.dump([{key: value} for key, value in out_data.items()], outfile, separators=(",", ":"))

    basemd5 = hashlib.md5()
    basemd5.update(new_rom_data)
    return "New Rom Hash: " + basemd5.hexdigest()


parse_yaml = functools.partial(load, Loader=Loader)


class Hint(typing.NamedTuple):
    receiving_player: int
    finding_player: int
    location: int
    item: int
    found: bool

def get_public_ipv4() -> str:
    import socket
    import urllib.request
    import logging
    ip = socket.gethostbyname(socket.gethostname())
    try:
        ip = urllib.request.urlopen('https://checkip.amazonaws.com/').read().decode('utf8').strip()
    except Exception as e:
        try:
            ip = urllib.request.urlopen('https://v4.ident.me').read().decode('utf8').strip()
        except:
            logging.exception(e)
            pass  # we could be offline, in a local game, so no point in erroring out
    return ip


_options = None


def get_options() -> dict:
    global _options
    if _options:
        return _options
    else:
        locations = ("options.yaml", "host.yaml",
                     local_path("options.yaml"), local_path("host.yaml"))

        for location in locations:
            if os.path.exists(location):
                with open(location) as f:
                    _options = parse_yaml(f.read())
                return _options
        raise FileNotFoundError(f"Could not find {locations[1]} to load options.")
