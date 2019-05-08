import argparse
import asyncio
import json
import logging
import re
import subprocess
import sys

import Items
import Regions

while True:
    try:
        import aioconsole
        break
    except ImportError:
        aioconsole = None
        print('Required python module "aioconsole" not found, press enter to install it')
        input()
        subprocess.call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'aioconsole'])

while True:
    try:
        import websockets
        break
    except ImportError:
        websockets = None
        print('Required python module "websockets" not found, press enter to install it')
        input()
        subprocess.call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'websockets'])

try:
    import colorama
except ImportError:
    colorama = None

class ReceivedItem:
    def __init__(self, item, location, player_id, player_name):
        self.item = item
        self.location = location
        self.player_id = player_id
        self.player_name = player_name

class Context:
    def __init__(self, snes_address, server_address, password, name, team, slot):
        self.snes_address = snes_address
        self.server_address = server_address

        self.exit_event = asyncio.Event()

        self.input_queue = asyncio.Queue()
        self.input_requests = 0

        self.snes_socket = None
        self.snes_state = SNES_DISCONNECTED
        self.snes_recv_queue = asyncio.Queue()
        self.snes_request_lock = asyncio.Lock()
        self.is_sd2snes = False
        self.snes_write_buffer = []

        self.server_task = None
        self.socket = None
        self.password = password

        self.name = name
        self.team = team
        self.slot = slot

        self.locations_checked = set()
        self.items_received = []
        self.last_rom = None
        self.expected_rom = None
        self.rom_confirmed = False

def color_code(*args):
    codes = {'reset': 0, 'bold': 1, 'underline': 4, 'black': 30, 'red': 31, 'green': 32, 'yellow': 33, 'blue': 34,
             'magenta': 35, 'cyan': 36, 'white': 37 , 'black_bg': 40, 'red_bg': 41, 'green_bg': 42, 'yellow_bg': 43,
             'blue_bg': 44, 'purple_bg': 45, 'cyan_bg': 46, 'white_bg': 47}
    return '\033[' + ';'.join([str(codes[arg]) for arg in args]) + 'm'

def color(text, *args):
    return color_code(*args) + text + color_code('reset')


ROM_START = 0x000000
WRAM_START = 0xF50000
WRAM_SIZE = 0x20000
SRAM_START = 0xE00000

ROMNAME_START = SRAM_START + 0x2000
ROMNAME_SIZE = 0x15

INGAME_MODES = {0x07, 0x09}

SAVEDATA_START = WRAM_START + 0xF000
SAVEDATA_SIZE = 0x500

RECV_PROGRESS_ADDR = SAVEDATA_START + 0x4D0 # 2 bytes
RECV_ITEM_ADDR = SAVEDATA_START + 0x4D2     # 1 byte


location_table = {'Mushroom': (0x411, 0x10),
                  'Bottle Merchant': (0x3C9, 0x02),
                  'Flute Spot': (0x2AA, 0x40),
                  'Sunken Treasure': (0x2BB, 0x40),
                  'Purple Chest': (0x3C9, 0x10),
                  'Blind\'s Hideout - Top': (0x23A, 0x10),
                  'Blind\'s Hideout - Left': (0x23A, 0x20),
                  'Blind\'s Hideout - Right': (0x23A, 0x40),
                  'Blind\'s Hideout - Far Left': (0x23A, 0x80),
                  'Blind\'s Hideout - Far Right': (0x23B, 0x01),
                  'Link\'s Uncle': (0x3C6, 0x01),
                  'Secret Passage': (0x0AA, 0x10),
                  'King Zora': (0x410, 0x02),
                  'Zora\'s Ledge': (0x301, 0x40),
                  'Waterfall Fairy - Left': (0x228, 0x10),
                  'Waterfall Fairy - Right': (0x228, 0x20),
                  'King\'s Tomb': (0x226, 0x10),
                  'Floodgate Chest': (0x216, 0x10),
                  'Link\'s House': (0x208, 0x10),
                  'Kakariko Tavern': (0x206, 0x10),
                  'Chicken House': (0x210, 0x10),
                  'Aginah\'s Cave': (0x214, 0x10),
                  'Sahasrahla\'s Hut - Left': (0x20A, 0x10),
                  'Sahasrahla\'s Hut - Middle': (0x20A, 0x20),
                  'Sahasrahla\'s Hut - Right': (0x20A, 0x40),
                  'Sahasrahla': (0x410, 0x10),
                  'Kakariko Well - Top': (0x05E, 0x10),
                  'Kakariko Well - Left': (0x05E, 0x20),
                  'Kakariko Well - Middle': (0x05E, 0x40),
                  'Kakariko Well - Right': (0x05E, 0x80),
                  'Kakariko Well - Bottom': (0x05F, 0x01),
                  'Blacksmith': (0x411, 0x04),
                  'Magic Bat': (0x411, 0x80),
                  'Sick Kid': (0x410, 0x04),
                  'Hobo': (0x3C9, 0x01),
                  'Lost Woods Hideout': (0x1C3, 0x02),
                  'Lumberjack Tree': (0x1C5, 0x02),
                  'Cave 45': (0x237, 0x04),
                  'Graveyard Cave': (0x237, 0x02),
                  'Checkerboard Cave': (0x24D, 0x02),
                  'Mini Moldorm Cave - Far Left': (0x246, 0x10),
                  'Mini Moldorm Cave - Left': (0x246, 0x20),
                  'Mini Moldorm Cave - Right': (0x246, 0x40),
                  'Mini Moldorm Cave - Far Right': (0x246, 0x80),
                  'Mini Moldorm Cave - Generous Guy': (0x247, 0x04),
                  'Ice Rod Cave': (0x240, 0x10),
                  'Bonk Rock Cave': (0x248, 0x10),
                  'Library': (0x410, 0x80),
                  'Potion Shop': (0x411, 0x20),
                  'Lake Hylia Island': (0x2B5, 0x40),
                  'Maze Race': (0x2A8, 0x40),
                  'Desert Ledge': (0x2B0, 0x40),
                  'Desert Palace - Big Chest': (0x0E6, 0x10),
                  'Desert Palace - Torch': (0x0E7, 0x04),
                  'Desert Palace - Map Chest': (0x0E8, 0x10),
                  'Desert Palace - Compass Chest': (0x10A, 0x10),
                  'Desert Palace - Big Key Chest': (0x0EA, 0x10),
                  'Desert Palace - Boss': (0x067, 0x08),
                  'Eastern Palace - Compass Chest': (0x150, 0x10),
                  'Eastern Palace - Big Chest': (0x152, 0x10),
                  'Eastern Palace - Cannonball Chest': (0x172, 0x10),
                  'Eastern Palace - Big Key Chest': (0x170, 0x10),
                  'Eastern Palace - Map Chest': (0x154, 0x10),
                  'Eastern Palace - Boss': (0x191, 0x08),
                  'Master Sword Pedestal': (0x300, 0x40),
                  'Hyrule Castle - Boomerang Chest': (0x0E2, 0x10),
                  'Hyrule Castle - Map Chest': (0x0E4, 0x10),
                  'Hyrule Castle - Zelda\'s Chest': (0x100, 0x10),
                  'Sewers - Dark Cross': (0x064, 0x10),
                  'Sewers - Secret Room - Left': (0x022, 0x10),
                  'Sewers - Secret Room - Middle': (0x022, 0x20),
                  'Sewers - Secret Room - Right': (0x022, 0x40),
                  'Sanctuary': (0x024, 0x10),
                  'Castle Tower - Room 03': (0x1C0, 0x10),
                  'Castle Tower - Dark Maze': (0x1A0, 0x10),
                  'Old Man': (0x410, 0x01),
                  'Spectacle Rock Cave': (0x1D5, 0x04),
                  'Paradox Cave Lower - Far Left': (0x1DE, 0x10),
                  'Paradox Cave Lower - Left': (0x1DE, 0x20),
                  'Paradox Cave Lower - Right': (0x1DE, 0x40),
                  'Paradox Cave Lower - Far Right': (0x1DE, 0x80),
                  'Paradox Cave Lower - Middle': (0x1DF, 0x01),
                  'Paradox Cave Upper - Left': (0x1FE, 0x10),
                  'Paradox Cave Upper - Right': (0x1FE, 0x20),
                  'Spiral Cave': (0x1FC, 0x10),
                  'Ether Tablet': (0x411, 0x01),
                  'Spectacle Rock': (0x283, 0x40),
                  'Tower of Hera - Basement Cage': (0x10F, 0x04),
                  'Tower of Hera - Map Chest': (0x0EE, 0x10),
                  'Tower of Hera - Big Key Chest': (0x10E, 0x10),
                  'Tower of Hera - Compass Chest': (0x04E, 0x20),
                  'Tower of Hera - Big Chest': (0x04E, 0x10),
                  'Tower of Hera - Boss': (0x00F, 0x08),
                  'Pyramid': (0x2DB, 0x40),
                  'Catfish': (0x410, 0x20),
                  'Stumpy': (0x410, 0x08),
                  'Digging Game': (0x2E8, 0x40),
                  'Bombos Tablet': (0x411, 0x02),
                  'Hype Cave - Top': (0x23C, 0x10),
                  'Hype Cave - Middle Right': (0x23C, 0x20),
                  'Hype Cave - Middle Left': (0x23C, 0x40),
                  'Hype Cave - Bottom': (0x23C, 0x80),
                  'Hype Cave - Generous Guy': (0x23D, 0x04),
                  'Peg Cave': (0x24F, 0x04),
                  'Pyramid Fairy - Left': (0x22C, 0x10),
                  'Pyramid Fairy - Right': (0x22C, 0x20),
                  'Brewery': (0x20C, 0x10),
                  'C-Shaped House': (0x238, 0x10),
                  'Chest Game': (0x20D, 0x04),
                  'Bumper Cave Ledge': (0x2CA, 0x40),
                  'Mire Shed - Left': (0x21A, 0x10),
                  'Mire Shed - Right': (0x21A, 0x20),
                  'Superbunny Cave - Top': (0x1F0, 0x10),
                  'Superbunny Cave - Bottom': (0x1F0, 0x20),
                  'Spike Cave': (0x22E, 0x10),
                  'Hookshot Cave - Top Right': (0x078, 0x10),
                  'Hookshot Cave - Top Left': (0x078, 0x20),
                  'Hookshot Cave - Bottom Right': (0x078, 0x80),
                  'Hookshot Cave - Bottom Left': (0x078, 0x40),
                  'Floating Island': (0x285, 0x40),
                  'Mimic Cave': (0x218, 0x10),
                  'Swamp Palace - Entrance': (0x050, 0x10),
                  'Swamp Palace - Map Chest': (0x06E, 0x10),
                  'Swamp Palace - Big Chest': (0x06C, 0x10),
                  'Swamp Palace - Compass Chest': (0x08C, 0x10),
                  'Swamp Palace - Big Key Chest': (0x06A, 0x10),
                  'Swamp Palace - West Chest': (0x068, 0x10),
                  'Swamp Palace - Flooded Room - Left': (0x0EC, 0x10),
                  'Swamp Palace - Flooded Room - Right': (0x0EC, 0x20),
                  'Swamp Palace - Waterfall Room': (0x0CC, 0x10),
                  'Swamp Palace - Boss': (0x00D, 0x08),
                  'Thieves\' Town - Big Key Chest': (0x1B6, 0x20),
                  'Thieves\' Town - Map Chest': (0x1B6, 0x10),
                  'Thieves\' Town - Compass Chest': (0x1B8, 0x10),
                  'Thieves\' Town - Ambush Chest': (0x196, 0x10),
                  'Thieves\' Town - Attic': (0x0CA, 0x10),
                  'Thieves\' Town - Big Chest': (0x088, 0x10),
                  'Thieves\' Town - Blind\'s Cell': (0x08A, 0x10),
                  'Thieves\' Town - Boss': (0x159, 0x08),
                  'Skull Woods - Compass Chest': (0x0CE, 0x10),
                  'Skull Woods - Map Chest': (0x0B0, 0x20),
                  'Skull Woods - Big Chest': (0x0B0, 0x10),
                  'Skull Woods - Pot Prison': (0x0AE, 0x20),
                  'Skull Woods - Pinball Room': (0x0D0, 0x10),
                  'Skull Woods - Big Key Chest': (0x0AE, 0x10),
                  'Skull Woods - Bridge Room': (0x0B2, 0x10),
                  'Skull Woods - Boss': (0x053, 0x08),
                  'Ice Palace - Compass Chest': (0x05C, 0x10),
                  'Ice Palace - Freezor Chest': (0x0FC, 0x10),
                  'Ice Palace - Big Chest': (0x13C, 0x10),
                  'Ice Palace - Iced T Room': (0x15C, 0x10),
                  'Ice Palace - Spike Room': (0x0BE, 0x10),
                  'Ice Palace - Big Key Chest': (0x03E, 0x10),
                  'Ice Palace - Map Chest': (0x07E, 0x10),
                  'Ice Palace - Boss': (0x1BD, 0x08),
                  'Misery Mire - Big Chest': (0x186, 0x10),
                  'Misery Mire - Map Chest': (0x186, 0x20),
                  'Misery Mire - Main Lobby': (0x184, 0x10),
                  'Misery Mire - Bridge Chest': (0x144, 0x10),
                  'Misery Mire - Spike Chest': (0x166, 0x10),
                  'Misery Mire - Compass Chest': (0x182, 0x10),
                  'Misery Mire - Big Key Chest': (0x1A2, 0x10),
                  'Misery Mire - Boss': (0x121, 0x08),
                  'Turtle Rock - Compass Chest': (0x1AC, 0x10),
                  'Turtle Rock - Roller Room - Left': (0x16E, 0x10),
                  'Turtle Rock - Roller Room - Right': (0x16E, 0x20),
                  'Turtle Rock - Chain Chomps': (0x16C, 0x10),
                  'Turtle Rock - Big Key Chest': (0x028, 0x10),
                  'Turtle Rock - Big Chest': (0x048, 0x10),
                  'Turtle Rock - Crystaroller Room': (0x008, 0x10),
                  'Turtle Rock - Eye Bridge - Bottom Left': (0x1AA, 0x80),
                  'Turtle Rock - Eye Bridge - Bottom Right': (0x1AA, 0x40),
                  'Turtle Rock - Eye Bridge - Top Left': (0x1AA, 0x20),
                  'Turtle Rock - Eye Bridge - Top Right': (0x1AA, 0x10),
                  'Turtle Rock - Boss': (0x149, 0x08),
                  'Palace of Darkness - Shooter Room': (0x012, 0x10),
                  'Palace of Darkness - The Arena - Bridge': (0x054, 0x20),
                  'Palace of Darkness - Stalfos Basement': (0x014, 0x10),
                  'Palace of Darkness - Big Key Chest': (0x074, 0x10),
                  'Palace of Darkness - The Arena - Ledge': (0x054, 0x10),
                  'Palace of Darkness - Map Chest': (0x056, 0x10),
                  'Palace of Darkness - Compass Chest': (0x034, 0x20),
                  'Palace of Darkness - Dark Basement - Left': (0x0D4, 0x10),
                  'Palace of Darkness - Dark Basement - Right': (0x0D4, 0x20),
                  'Palace of Darkness - Dark Maze - Top': (0x032, 0x10),
                  'Palace of Darkness - Dark Maze - Bottom': (0x032, 0x20),
                  'Palace of Darkness - Big Chest': (0x034, 0x10),
                  'Palace of Darkness - Harmless Hellway': (0x034, 0x40),
                  'Palace of Darkness - Boss': (0x0B5, 0x08),
                  'Ganons Tower - Bob\'s Torch': (0x119, 0x04),
                  'Ganons Tower - Hope Room - Left': (0x118, 0x20),
                  'Ganons Tower - Hope Room - Right': (0x118, 0x40),
                  'Ganons Tower - Tile Room': (0x11A, 0x10),
                  'Ganons Tower - Compass Room - Top Left': (0x13A, 0x10),
                  'Ganons Tower - Compass Room - Top Right': (0x13A, 0x20),
                  'Ganons Tower - Compass Room - Bottom Left': (0x13A, 0x40),
                  'Ganons Tower - Compass Room - Bottom Right': (0x13A, 0x80),
                  'Ganons Tower - DMs Room - Top Left': (0x0F6, 0x10),
                  'Ganons Tower - DMs Room - Top Right': (0x0F6, 0x20),
                  'Ganons Tower - DMs Room - Bottom Left': (0x0F6, 0x40),
                  'Ganons Tower - DMs Room - Bottom Right': (0x0F6, 0x80),
                  'Ganons Tower - Map Chest': (0x116, 0x10),
                  'Ganons Tower - Firesnake Room': (0x0FA, 0x10),
                  'Ganons Tower - Randomizer Room - Top Left': (0x0F8, 0x10),
                  'Ganons Tower - Randomizer Room - Top Right': (0x0F8, 0x20),
                  'Ganons Tower - Randomizer Room - Bottom Left': (0x0F8, 0x40),
                  'Ganons Tower - Randomizer Room - Bottom Right': (0x0F8, 0x80),
                  'Ganons Tower - Bob\'s Chest': (0x118, 0x80),
                  'Ganons Tower - Big Chest': (0x118, 0x10),
                  'Ganons Tower - Big Key Room - Left': (0x038, 0x20),
                  'Ganons Tower - Big Key Room - Right': (0x038, 0x40),
                  'Ganons Tower - Big Key Chest': (0x038, 0x10),
                  'Ganons Tower - Mini Helmasaur Room - Left': (0x07A, 0x10),
                  'Ganons Tower - Mini Helmasaur Room - Right': (0x07A, 0x20),
                  'Ganons Tower - Pre-Moldorm Chest': (0x07A, 0x40),
                  'Ganons Tower - Validation Chest': (0x09A, 0x10)
                  }

SNES_DISCONNECTED = 0
SNES_CONNECTING = 1
SNES_CONNECTED = 2
SNES_ATTACHED = 3

async def snes_connect(ctx : Context, address = None):
    if ctx.snes_socket is not None:
        print('Already connected to snes')
        return

    ctx.snes_state = SNES_CONNECTING
    recv_task = None

    if address is None:
        address = 'ws://' + ctx.snes_address

    print("Connecting to QUsb2snes at %s ..." % address)

    try:
        ctx.snes_socket = await websockets.connect(address, ping_timeout=None)
        ctx.snes_state = SNES_CONNECTED

        DeviceList_Request = {
            "Opcode" : "DeviceList",
            "Space" : "SNES"
        }
        await ctx.snes_socket.send(json.dumps(DeviceList_Request))

        reply = json.loads(await ctx.snes_socket.recv())
        devices = reply['Results'] if 'Results' in reply and len(reply['Results']) > 0 else None

        if not devices:
            raise Exception('No device found')

        print("Available devices:")
        for id, device in enumerate(devices):
            print("[%d] %s" % (id + 1, device))

        device = None
        while True:
            print("Enter a number:")
            choice = await console_input(ctx)
            if choice is None:
                raise Exception('Abort input')
            if not choice.isdigit() or int(choice) < 1 or int(choice) > len(devices):
                print("Invalid choice (%s)" % choice)
                continue

            device = devices[int(choice) - 1]
            break

        print("Attaching to " + device)

        Attach_Request = {
            "Opcode" : "Attach",
            "Space" : "SNES",
            "Operands" : [device]
        }
        await ctx.snes_socket.send(json.dumps(Attach_Request))
        ctx.snes_state = SNES_ATTACHED

        if 'SD2SNES'.lower() in device.lower():
            print("SD2SNES Detected")
            ctx.is_sd2snes = True
            await ctx.snes_socket.send(json.dumps({"Opcode" : "Info", "Space" : "SNES"}))
            reply = json.loads(await ctx.snes_socket.recv())
            if reply and 'Results' in reply:
                print(reply['Results'])
        else:
            ctx.is_sd2snes = False

        recv_task = asyncio.create_task(snes_recv_loop(ctx))

    except Exception as e:
        print("Error connecting to snes (%s)" % e)
        if recv_task is not None:
            if not ctx.snes_socket.closed:
                await ctx.snes_socket.close()
        else:
            if ctx.snes_socket is not None:
                if not ctx.snes_socket.closed:
                    await ctx.snes_socket.close()
                ctx.snes_socket = None
            ctx.snes_state = SNES_DISCONNECTED

async def snes_recv_loop(ctx : Context):
    try:
        async for msg in ctx.snes_socket:
            ctx.snes_recv_queue.put_nowait(msg)
        print("Snes disconnected, type /snes to reconnect")
    except Exception as e:
        print("Lost connection to the snes, type /snes to reconnect")
        if type(e) is not websockets.ConnectionClosed:
            logging.exception(e)
    finally:
        socket, ctx.snes_socket = ctx.snes_socket, None
        if socket is not None and not socket.closed:
            await socket.close()

        ctx.snes_state = SNES_DISCONNECTED
        ctx.snes_recv_queue = asyncio.Queue()

async def snes_read(ctx : Context, address, size):
    try:
        await ctx.snes_request_lock.acquire()

        if ctx.snes_state != SNES_ATTACHED or ctx.snes_socket is None or not ctx.snes_socket.open or ctx.snes_socket.closed:
            return None

        GetAddress_Request = {
            "Opcode" : "GetAddress",
            "Space" : "SNES",
            "Operands" : [hex(address)[2:], hex(size)[2:]]
        }
        try:
            await ctx.snes_socket.send(json.dumps(GetAddress_Request))
        except websockets.ConnectionClosed:
            return None

        data = bytes()
        while len(data) < size:
            try:
                data += await asyncio.wait_for(ctx.snes_recv_queue.get(), 5)
            except asyncio.TimeoutError:
                break

        if len(data) != size:
            print('Error reading %s, requested %d bytes, received %d' % (hex(address), size, len(data)))
            if len(data):
                print(str(data))
            if ctx.snes_socket is not None and not ctx.snes_socket.closed:
                await ctx.snes_socket.close()
            return None

        return data
    finally:
        ctx.snes_request_lock.release()

async def snes_write(ctx : Context, write_list):
    try:
        await ctx.snes_request_lock.acquire()

        if ctx.snes_state != SNES_ATTACHED or ctx.snes_socket is None or not ctx.snes_socket.open or ctx.snes_socket.closed:
            return False

        PutAddress_Request = {
            "Opcode" : "PutAddress",
            "Operands" : []
        }

        if ctx.is_sd2snes:
            cmd = b'\x00\xE2\x20\x48\xEB\x48'

            for address, data in write_list:
                if (address < WRAM_START) or ((address + len(data)) > (WRAM_START + WRAM_SIZE)):
                    print("SD2SNES: Write out of range %s (%d)" % (hex(address), len(data)))
                    return False
                for ptr, byte in enumerate(data, address + 0x7E0000 - WRAM_START):
                    #todo: can this be optimized ?
                    cmd += b'\xA9' # LDA
                    cmd += bytes([byte])
                    cmd += b'\x8F' # STA.l
                    cmd += bytes([ptr & 0xFF, (ptr >> 8) & 0xFF, (ptr >> 16) & 0xFF])

            cmd += b'\xA9\x00\x8F\x00\x2C\x00\x68\xEB\x68\x28\x6C\xEA\xFF\x08'

            PutAddress_Request['Space'] = 'CMD'
            PutAddress_Request['Operands'] = ["2C00", hex(len(cmd)-1)[2:], "2C00", "1"]
            try:
                if ctx.snes_socket is not None:
                    await ctx.snes_socket.send(json.dumps(PutAddress_Request))
                if ctx.snes_socket is not None:
                    await ctx.snes_socket.send(cmd)
            except websockets.ConnectionClosed:
                return False
        else:
            PutAddress_Request['Space'] = 'SNES'
            try:
                #will pack those requests as soon as qusb2snes actually supports that for real
                for address, data in write_list:
                    PutAddress_Request['Operands'] = [hex(address)[2:], hex(len(data))[2:]]
                    if ctx.snes_socket is not None:
                        await ctx.snes_socket.send(json.dumps(PutAddress_Request))
                    if ctx.snes_socket is not None:
                        await ctx.snes_socket.send(data)
            except websockets.ConnectionClosed:
                return False

        return True
    finally:
        ctx.snes_request_lock.release()

def snes_buffered_write(ctx : Context, address, data):
    ctx.snes_write_buffer.append((address, data))

async def snes_flush_writes(ctx : Context):
    if not ctx.snes_write_buffer:
        return

    await snes_write(ctx, ctx.snes_write_buffer)
    ctx.snes_write_buffer = []

async def send_msgs(websocket, msgs):
    if not websocket or not websocket.open or websocket.closed:
        return
    try:
        await websocket.send(json.dumps(msgs))
    except websockets.ConnectionClosed:
        pass

def rom_confirmed(ctx : Context):
    ctx.rom_confirmed = True
    print('ROM hash Confirmed')

async def server_loop(ctx : Context):
    if ctx.socket is not None:
        print('Already connected')
        return

    while not ctx.server_address:
        print('Enter multiworld server address')
        ctx.server_address = await console_input(ctx)

    address = 'ws://' + ctx.server_address

    print('Connecting to multiworld server at %s' % address)
    try:
        ctx.socket = await websockets.connect(address, ping_timeout=None)
        print('Connected')

        async for data in ctx.socket:
            for msg in json.loads(data):
                if len(msg) == 1:
                    cmd = msg
                    args = None
                else:
                    cmd = msg[0]
                    args = msg[1]
                await process_server_cmd(ctx, cmd, args)
        print('Disconnected from multiworld server, type /connect to reconnect')
    except ConnectionRefusedError:
        print('Connection refused by the multiworld server')
    except Exception as e:
        print('Lost connection to the multiworld server, type /connect to reconnect')
        if type(e) is not websockets.ConnectionClosed:
            logging.exception(e)
    finally:
        ctx.name = None
        ctx.team = None
        ctx.slot = None
        ctx.expected_rom = None
        ctx.rom_confirmed = False
        socket, ctx.socket = ctx.socket, None
        if socket is not None and not socket.closed:
            await socket.close()
        ctx.server_task = None

async def process_server_cmd(ctx : Context, cmd, args):
    if cmd == 'RoomInfo':
        print('--------------------------------')
        print('Room Information:')
        print('--------------------------------')
        if args['password']:
            print('Password required')
        print('%d players seed' % args['slots'])
        if len(args['players']) < 1:
            print('No player connected')
        else:
            args['players'].sort(key=lambda player: ('' if not player[1] else player[1].lower(), player[2]))
            current_team = 0
            print('Connected players:')
            for name, team, slot in args['players']:
                if team != current_team:
                    print('  Default team' if not team else '  Team: %s' % team)
                    current_team = team
                print('    %s (Player %d)' % (name, slot))
        await server_auth(ctx, args['password'])

    if cmd == 'ConnectionRefused':
        password_requested = False
        if 'InvalidPassword' in args:
            print('Invalid password')
            ctx.password = None
            password_requested = True
        if 'InvalidName' in args:
            print('Invalid name')
            ctx.name = None
        if 'NameAlreadyTaken' in args:
            print('Name already taken')
            ctx.name = None
        if 'InvalidTeam' in args:
            print('Invalid team name')
            ctx.team = None
        if 'InvalidSlot' in args:
            print('Invalid player slot')
            ctx.slot = None
        if 'SlotAlreadyTaken' in args:
            print('Player slot already in use for that team')
            ctx.team = None
            ctx.slot = None
        await server_auth(ctx, password_requested)

    if cmd == 'Connected':
        ctx.expected_rom = args
        if ctx.last_rom == ctx.expected_rom:
            rom_confirmed(ctx)
            if ctx.locations_checked:
                await send_msgs(ctx.socket, [['LocationChecks', [Regions.location_table[loc][0] for loc in ctx.locations_checked]]])
        elif ctx.last_rom is not None:
            raise Exception('Different ROM expected from server')

    if cmd == 'ReceivedItems':
        start_index, items = args
        if start_index == 0:
            ctx.items_received = []
        elif start_index != len(ctx.items_received):
            sync_msg = [['Sync']]
            if ctx.locations_checked:
                sync_msg.append(['LocationChecks', [Regions.location_table[loc][0] for loc in ctx.locations_checked]])
            await send_msgs(ctx.socket, sync_msg)
        if start_index == len(ctx.items_received):
            for item in items:
                ctx.items_received.append(ReceivedItem(item[0], item[1], item[2], item[3]))

    if cmd == 'ItemSent':
        player_sent, player_recvd, item, location = args
        item = color(get_item_name_from_id(item), 'cyan' if player_sent != ctx.name else 'green')
        player_sent = color(player_sent, 'yellow' if player_sent != ctx.name else 'magenta')
        player_recvd = color(player_recvd, 'yellow' if player_recvd != ctx.name else 'magenta')
        print('(%s) %s sent %s to %s (%s)' % (ctx.team if ctx.team else 'Team', player_sent, item, player_recvd, get_location_name_from_address(location)))

    if cmd == 'Print':
        print(args)

async def server_auth(ctx : Context, password_requested):
    if password_requested and not ctx.password:
        print('Enter the password required to join this game:')
        ctx.password = await console_input(ctx)
    while not ctx.name or not re.match(r'\w{1,10}', ctx.name):
        print('Enter your name (10 characters):')
        ctx.name = await console_input(ctx)
    if not ctx.team:
        print('Enter your team name (optional):')
        ctx.team = await console_input(ctx)
        if ctx.team == '': ctx.team = None
    if not ctx.slot:
        print('Choose your player slot (optional):')
        slot = await console_input(ctx)
        ctx.slot = int(slot) if slot.isdigit() else None
    await send_msgs(ctx.socket, [['Connect', {'password': ctx.password, 'name': ctx.name, 'team': ctx.team, 'slot': ctx.slot}]])

async def console_input(ctx : Context):
    ctx.input_requests += 1
    return await ctx.input_queue.get()

async def console_loop(ctx : Context):
    while not ctx.exit_event.is_set():
        input = await aioconsole.ainput()

        if ctx.input_requests > 0:
            ctx.input_requests -= 1
            ctx.input_queue.put_nowait(input)
            continue

        command = input.split()
        if not command:
            continue

        if command[0] == '/exit':
            ctx.exit_event.set()

        if command[0] == '/installcolors' and 'colorama' not in sys.modules:
            subprocess.call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'colorama'])
            global colorama
            import colorama
            colorama.init()

        if command[0] == '/snes':
            asyncio.create_task(snes_connect(ctx, command[1] if len(command) > 1 else None))
        if command[0] in ['/snes_close', '/snes_quit']:
            if ctx.snes_socket is not None and not ctx.snes_socket.closed:
                await ctx.snes_socket.close()

        async def disconnect():
            if ctx.socket is not None and not ctx.socket.closed:
                await ctx.socket.close()
            if ctx.server_task is not None:
                await ctx.server_task
        async def connect():
            await disconnect()
            ctx.server_task = asyncio.create_task(server_loop(ctx))

        if command[0] in ['/connect', '/reconnect']:
            if len(command) > 1:
                ctx.server_address = command[1]
            asyncio.create_task(connect())
        if command[0] == '/disconnect':
            asyncio.create_task(disconnect())
        if command[0][:1] != '/':
            asyncio.create_task(send_msgs(ctx.socket, [['Say', input]]))

        if command[0] == '/received':
            print('Received items:')
            for index, item in enumerate(ctx.items_received, 1):
                print('%s from %s (%s) (%d/%d in list)' % (
                    color(get_item_name_from_id(item.item), 'red', 'bold'), color(item.player_name, 'yellow'),
                    get_location_name_from_address(item.location), index, len(ctx.items_received)))

        if command[0] == '/missing':
            for location in location_table.keys():
                if location not in ctx.locations_checked:
                    print('Missing: ' + location)
        if command[0] == '/getitem' and len(command) > 1:
            item = input[9:]
            item_id = Items.item_table[item][3] if item in Items.item_table else None
            if type(item_id) is int and item_id in range(0x100):
                print('Sending item: ' + item)
                snes_buffered_write(ctx, RECV_ITEM_ADDR, bytes([item_id]))
            else:
                print('Invalid item: ' + item)

        await snes_flush_writes(ctx)

def get_item_name_from_id(code):
    items = [k for k, i in Items.item_table.items() if type(i[3]) is int and i[3] == code]
    return items[0] if items else 'Unknown item'

def get_location_name_from_address(address):
    if type(address) is str:
        return address

    locs = [k for k, l in Regions.location_table.items() if type(l[0]) is int and l[0] == address]
    return locs[0] if locs else 'Unknown location'

async def game_watcher(ctx : Context):
    while not ctx.exit_event.is_set():
        await asyncio.sleep(1)

        if not ctx.rom_confirmed:
            rom = await snes_read(ctx, ROMNAME_START, ROMNAME_SIZE)
            if rom is None or rom == bytes([0] * ROMNAME_SIZE):
                continue
            if list(rom) != ctx.last_rom:
                ctx.last_rom = list(rom)
                ctx.locations_checked = set()
            if ctx.expected_rom is not None:
                if ctx.last_rom != ctx.expected_rom:
                    print("Wrong ROM detected")
                    await ctx.snes_socket.close()
                    continue
                else:
                    rom_confirmed(ctx)

        gamemode = await snes_read(ctx, WRAM_START + 0x10, 1)
        if gamemode is None or gamemode[0] not in INGAME_MODES:
            continue

        data = await snes_read(ctx, SAVEDATA_START, 0x412)
        if data is None:
            continue
        for location, (offset, mask) in location_table.items():
            if data[offset] & mask != 0 and location not in ctx.locations_checked:
                ctx.locations_checked.add(location)
                print("New check: %s (%d/216)" % (location, len(ctx.locations_checked)))
                await send_msgs(ctx.socket, [['LocationChecks', [Regions.location_table[location][0]]]])

        data = await snes_read(ctx, RECV_PROGRESS_ADDR, 3)
        if data is None:
            continue
        recv_index = data[0] + (data[1] * 0x100)
        assert(RECV_ITEM_ADDR == RECV_PROGRESS_ADDR + 2)
        recving = data[2]
        if recv_index < len(ctx.items_received) and recving == 0:
            item = ctx.items_received[recv_index]
            print('Received %s from %s (%s) (%d/%d in list)' % (
                color(get_item_name_from_id(item.item), 'red', 'bold'), color(item.player_name, 'yellow'),
                get_location_name_from_address(item.location), recv_index + 1, len(ctx.items_received)))
            recv_index += 1
            snes_buffered_write(ctx, RECV_PROGRESS_ADDR, bytes([recv_index & 0xFF, (recv_index >> 8) & 0xFF]))
            snes_buffered_write(ctx, RECV_ITEM_ADDR, bytes([item.item]))

        await snes_flush_writes(ctx)

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snes', default='localhost:8080', help='Address of the QUsb2snes server.')
    parser.add_argument('--connect', default=None, help='Address of the multiworld host.')
    parser.add_argument('--password', default=None, help='Password of the multiworld host.')
    parser.add_argument('--name', default=None)
    parser.add_argument('--team', default=None)
    parser.add_argument('--slot', default=None, type=int)
    args = parser.parse_args()

    ctx = Context(args.snes, args.connect, args.password, args.name, args.team, args.slot)

    input_task = asyncio.create_task(console_loop(ctx))

    await snes_connect(ctx)

    if ctx.server_task is None:
        ctx.server_task = asyncio.create_task(server_loop(ctx))

    watcher_task = asyncio.create_task(game_watcher(ctx))


    await ctx.exit_event.wait()


    await watcher_task

    if ctx.socket is not None and not ctx.socket.closed:
        await ctx.socket.close()
    if ctx.server_task is not None:
        await ctx.server_task

    if ctx.snes_socket is not None and not ctx.snes_socket.closed:
        await ctx.snes_socket.close()

    while ctx.input_requests > 0:
        ctx.input_queue.put_nowait(None)
        ctx.input_requests -= 1

    await input_task

if __name__ == '__main__':
    if 'colorama' in sys.modules:
        colorama.init()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.run_until_complete(asyncio.gather(*asyncio.Task.all_tasks()))
    loop.close()

    if 'colorama' in sys.modules:
        colorama.deinit()
