import aioconsole
import argparse
import asyncio
import json
import re
import websockets
import winsound

ROM_START = 0x000000
WRAM_START = 0xF50000
SRAM_START = 0xE00000

ROMNAME_START = SRAM_START + 0x2000
ROMNAME_SIZE = 0x15

INGAME_MODES = {0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x15, 0x16, 0x18, 0x19}

SAVEDATA_START = WRAM_START + 0xF000
SAVEDATA_SIZE = 0x500

RECV_PROGRESS_ADDR = SAVEDATA_START + 0x4D0 # 2 bytes

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

async def snes_connect(ctx, address = None):
    if ctx.snes_socket is not None:
        print('Already connected to snes')
        return

    ctx.snes_state = SNES_CONNECTING

    if address is None:
        address = 'ws://' + ctx.snes_address

    print("Connecting to QUsb2snes at %s ..." % address)

    try:
        ctx.snes_socket = await websockets.connect(address)
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

        asyncio.create_task(snes_recv_loop(ctx))

    except Exception as e:
        print("Error connecting to snes (%s)" % e)
        if ctx.snes_state == SNES_CONNECTING:
            ctx.snes_state = SNES_DISCONNECTED
        if ctx.snes_socket is not None and not ctx.snes_socket.closed:
            await ctx.snes_socket.close()
        return

async def snes_recv_loop(ctx):
    requests_task = asyncio.create_task(snes_requests_loop(ctx))
    try:
        async for msg in ctx.snes_socket:
            ctx.snes_recv_queue.put_nowait(msg)
        print("Snes disconnected, type /snes to reconnect")
    except Exception as e:
        print("Lost connection to the snes, type /snes to reconnect (Error: %s)" % e)
    finally:
        requests_task.cancel()
        await requests_task

        socket, ctx.snes_socket = ctx.snes_socket, None
        if socket is not None and not socket.closed:
            await socket.close()

        ctx.snes_state = SNES_DISCONNECTED
        ctx.snes_recv_queue = asyncio.Queue()

async def snes_requests_loop(ctx):
    try:
        ctx.snes_request_queue = asyncio.Queue()
        while True:
            co, fut = await ctx.snes_request_queue.get()
            fut.set_result(await co)
    except (asyncio.CancelledError, websockets.ConnectionClosed):
        while not ctx.snes_request_queue.empty():
            co, fut = ctx.snes_request_queue.get_nowait()
            fut.set_result(None)
    finally:
        ctx.snes_request_queue = None

async def snes_read_co(ctx, address, size):
    if ctx.snes_socket is None or not ctx.snes_socket.open or ctx.snes_socket.closed:
        return None

    GetAddress_Request = {
        "Opcode" : "GetAddress",
        "Space" : "SNES",
        "Operands" : [hex(address)[2:], hex(size)[2:]]
    }
    await ctx.snes_socket.send(json.dumps(GetAddress_Request))

    data = bytes()
    while len(data) < size:
        data += await ctx.snes_recv_queue.get()

    if len(data) != size:
        print('Error reading %s, requested %d bytes, received %d' % (hex(address), size, len(data)))
        return None

    return data

async def snes_read(ctx, address, size):
    if ctx.snes_request_queue is None:
        return None
    future = asyncio.get_running_loop().create_future()
    ctx.snes_request_queue.put_nowait((snes_read_co(ctx, address, size), future))
    return await future

async def snes_write_co(ctx, address, data):
    if ctx.snes_socket is None or not ctx.snes_socket.open or ctx.snes_socket.closed:
        return False

    PutAddress_Request = {
        "Opcode" : "PutAddress",
        "Space" : "SNES",
        "Operands" : [hex(address)[2:], hex(len(data))[2:]]
    }
    await ctx.snes_socket.send(json.dumps(PutAddress_Request))
    await ctx.snes_socket.send(data)

    return True

async def snes_write(ctx, address, data):
    if ctx.snes_request_queue is None:
        return None
    future = asyncio.get_running_loop().create_future()
    ctx.snes_request_queue.put_nowait((snes_write_co(ctx, address, data), future))
    return await future

async def send_msgs(websocket, msgs):
    if not websocket or not websocket.open or websocket.closed:
        return
    await websocket.send(json.dumps(msgs))

async def server_loop(ctx):
    if ctx.socket is not None:
        print('Already connected')
        return

    while not ctx.server_address:
        print('Enter multiworld server address')
        ctx.server_address = await console_input(ctx)

    address = 'ws://' + ctx.server_address

    print('Connecting to multiworld server at %s' % address)
    try:
        ctx.socket = await websockets.connect(address)
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
    except Exception as e:
        print('Disconnected from multiworld server, type /connect to reconnect (Error: %s)' % e)
    finally:
        ctx.name = None
        ctx.team = None
        ctx.slot = None
        ctx.expected_rom = None
        socket, ctx.socket = ctx.socket, None
        if socket is not None and not socket.closed:
            await socket.close()
        ctx.server_task = None

async def process_server_cmd(ctx, cmd, args):
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
        if ctx.last_rom is not None and ctx.last_rom != ctx.expected_rom:
            raise Exception('Different ROM expected from server')
        if ctx.locations_checked:
            await send_msgs(ctx.socket, [['LocationChecks', list(ctx.locations_checked)]])

    if cmd == 'ReceivedItems':
        start_index, items = args
        if start_index == 0:
            ctx.items_received = []
        elif start_index != len(ctx.items_received):
            sync_msg = [['Sync']]
            if ctx.locations_checked:
                sync_msg.append(['LocationChecks', list(ctx.locations_checked)])
            await send_msgs(ctx.socket, sync_msg)
        if start_index == len(ctx.items_received):
            for item in items:
                ctx.items_received.append(ReceivedItem(item[0], item[1], item[2], item[3]))

    if cmd == 'Print':
        print(args)

async def server_auth(ctx, password_requested):
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

async def console(ctx):
    try:
        while True:
            input = await aioconsole.ainput()

            if ctx.input_requests > 0:
                ctx.input_requests -= 1
                ctx.input_queue.put_nowait(input)
                continue

            command = input.split()
            if not command:
                continue

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

            if command[0] == '/missing':
                for location, (offset, mask) in location_table.items():
                    if location not in ctx.locations_checked:
                        print('Missing: ' + location)
            if command[0] == '/maxkeys':
                await snes_write(ctx, SAVEDATA_START + 0x364, b'\xFF\xFF\xFF\xFF\xFF\xFF')
                await snes_write(ctx, SAVEDATA_START + 0x36F, b'\x63')
                await snes_write(ctx, SAVEDATA_START + 0x37C, b'\x63\x63\x63\x63\x63\x63\x63\x63\x63\x63\x63\x63\x63\x63\x63\x63')
            if command[0] == '/nokey':
                await snes_write(ctx, SAVEDATA_START + 0x364, b'\x00\x00\x00\x00\x00\x00')
                await snes_write(ctx, SAVEDATA_START + 0x36F, b'\x00')
                await snes_write(ctx, SAVEDATA_START + 0x37C, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
            if command[0] == '/getitem' and len(command) > 1:
                await inject_item(ctx, input[9:])

    except asyncio.CancelledError:
        pass

async def console_input(ctx):
    ctx.input_requests += 1
    return await ctx.input_queue.get()

async def game_watcher(ctx):
    try:
        while True:
            await asyncio.sleep(1)

            rom = await snes_read(ctx, ROMNAME_START, ROMNAME_SIZE)
            if rom is None:
                continue
            if list(rom) != ctx.last_rom:
                ctx.last_rom = list(rom)
                ctx.locations_checked = set()
            if ctx.expected_rom is not None and ctx.last_rom != ctx.expected_rom:
                print("Wrong ROM detected")
                await ctx.snes_socket.close()
                continue

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
                    await send_msgs(ctx.socket, [['LocationChecks', [location]]])

            data = await snes_read(ctx, RECV_PROGRESS_ADDR, 2)
            if data is None:
                continue
            recv_index = data[0] + (data[1] * 0x100)
            if recv_index < len(ctx.items_received):
                item = ctx.items_received[recv_index]
                winsound.PlaySound('itemget.wav', winsound.SND_FILENAME | winsound.SND_ASYNC)
                print('Received %s from %s (Player %d) (%s)' % (item.name, item.player_name, item.player_id, item.location))
                await inject_item(ctx, item.name)
                recv_index += 1
                await snes_write(ctx, RECV_PROGRESS_ADDR, bytes([recv_index & 0xFF, (recv_index >> 8) & 0xFF]))

    except asyncio.CancelledError:
        pass

async def inject_item(ctx, name):
    inv_swap = {'Blue Boomerang': 0x80, 'Red Boomerang': 0x40, 'Mushroom': 0x20, 'Magic Powder': 0x10, 'Shovel': 0x04, 'Ocarina': 0x02}
    if name in inv_swap:
        cur = await snes_read(ctx, SAVEDATA_START + 0x38C, 1)
        if cur is None:
            return
        target = cur[0] | inv_swap[name]
        await snes_write(ctx, SAVEDATA_START + 0x38C, bytes([target]))

        if name in ['Blue Boomerang', 'Red Boomerang']:
            has_redboom = bool(target & inv_swap['Red Boomerang'])
            await snes_write(ctx, SAVEDATA_START + 0x341, bytes([2 if has_redboom else 1]))

        if name in ['Mushroom', 'Magic Powder']:
            has_powder = bool(target & inv_swap['Magic Powder'])
            await snes_write(ctx, SAVEDATA_START + 0x344, bytes([2 if has_powder else 1]))

        if name in ['Shovel', 'Ocarina']:
            has_ocarina = bool(target & inv_swap['Ocarina'])
            ocarina_active =  bool(target & 0x01)
            await snes_write(ctx, SAVEDATA_START + 0x34C, bytes([3 if ocarina_active else (2 if has_ocarina else 1)]))

        return

    inv_swap2 = {'Bow': 0x80, 'Silver Arrows': 0x40}
    if name in inv_swap2:
        cur = await snes_read(ctx, SAVEDATA_START + 0x38E, 1)
        if cur is None:
            return
        target = cur[0] | inv_swap2[name]
        await snes_write(ctx, SAVEDATA_START + 0x38E, bytes([target]))

        has_bow = bool(target & inv_swap2['Bow'])
        has_silvers = bool(target & inv_swap2['Silver Arrows'])
        if has_bow:
            await snes_write(ctx, SAVEDATA_START + 0x340, bytes([4 if has_silvers else 2]))

        return

    if name in ['Big Key (Eastern Palace)', 'Compass (Eastern Palace)', 'Map (Eastern Palace)',
                'Big Key (Desert Palace)', 'Compass (Desert Palace)', 'Map (Desert Palace)',
                'Big Key (Tower of Hera)', 'Compass (Tower of Hera)', 'Map (Tower of Hera)',
                'Big Key (Escape)', 'Compass (Escape)', 'Map (Escape)',
                'Big Key (Palace of Darkness)', 'Compass (Palace of Darkness)', 'Map (Palace of Darkness)',
                'Big Key (Thieves Town)', 'Compass (Thieves Town)', 'Map (Thieves Town)',
                'Big Key (Skull Woods)', 'Compass (Skull Woods)', 'Map (Skull Woods)',
                'Big Key (Swamp Palace)', 'Compass (Swamp Palace)', 'Map (Swamp Palace)',
                'Big Key (Ice Palace)', 'Compass (Ice Palace)', 'Map (Ice Palace)',
                'Big Key (Misery Mire)', 'Compass (Misery Mire)', 'Map (Misery Mire)',
                'Big Key (Turtle Rock)', 'Compass (Turtle Rock)', 'Map (Turtle Rock)',
                'Big Key (Ganons Tower)', 'Compass (Ganons Tower)', 'Map (Ganons Tower)']:
        address = 0x364
        if name[:7] == 'Big Key':
            address = 0x366
        if name[:3] == 'Map':
            address = 0x368
        dungeons = {'(Ganons Tower)': (0, 0x04), '(Turtle Rock)': (0, 0x08), '(Thieves Town)': (0, 0x10), '(Tower of Hera)': (0, 0x20), '(Ice Palace)': (0, 0x40), '(Skull Woods)': (0, 0x80),
                    '(Misery Mire)': (1, 0x01), '(Palace of Darkness)': (1, 0x02), '(Swamp Palace)': (1, 0x04), '(Desert Palace)': (1, 0x10), '(Eastern Palace)': (1, 0x20), '(Escape)': (1, 0xC0)}
        for dungeon, (offset, mask) in dungeons.items():
            if dungeon in name:
                cur = await snes_read(ctx, SAVEDATA_START + address + offset, 1)
                if cur is not None:
                    await snes_write(ctx, SAVEDATA_START + address + offset, bytes([cur[0] | mask]))
                return

    async def send_key(dungeonoffset, dungeonid):
        buf1 = await snes_read(ctx, WRAM_START + 0x40C, 1)
        if buf1 is not None:
            if buf1[0] == dungeonid:
                buf2 = await snes_read(ctx, SAVEDATA_START + 0x36F, 1)
                if buf2 is not None:
                    await snes_write(ctx, SAVEDATA_START + 0x36F, bytes([buf2[0] + 1]))
            buf3 = await snes_read(ctx, SAVEDATA_START + dungeonoffset, 1)
            if buf3 is not None:
                await snes_write(ctx, SAVEDATA_START + dungeonoffset, bytes([buf3[0] + 1]))

    dungeons_keys = {'Small Key (Eastern Palace)': (0x37E, 0x04), 'Small Key (Desert Palace)': (0x37F, 0x06),
                     'Small Key (Tower of Hera)': (0x386, 0x14), 'Small Key (Agahnims Tower)': (0x380, 0x08),
                     'Small Key (Palace of Darkness)': (0x382, 0x0c), 'Small Key (Thieves Town)': (0x387, 0x16),
                     'Small Key (Skull Woods)': (0x384, 0x10), 'Small Key (Swamp Palace)': (0x381, 0x0a),
                     'Small Key (Ice Palace)': (0x385, 0x12), 'Small Key (Misery Mire)': (0x383, 0x0e),
                     'Small Key (Turtle Rock)': (0x388, 0x18), 'Small Key (Ganons Tower)': (0x389, 0x1a)}
    if name == 'Small Key (Escape)':
        await send_key(0x37C, 0x00)
        await send_key(0x37D, 0x02)
        return
    if name in dungeons_keys:
        await send_key(dungeons_keys[name][0], dungeons_keys[name][1])
        return

    magics = {'Magic Upgrade (1/2)': 1, 'Magic Upgrade (1/4)': 2}
    if name in magics:
        cur = await snes_read(ctx, SAVEDATA_START + 0x37B, 1)
        if cur is None or cur[0] >= magics[name]:
            return
        await snes_write(ctx, SAVEDATA_START + 0x37B, bytes([magics[name]]))
        await snes_write(ctx, SAVEDATA_START + 0x373, bytes([0x80]))
        return

    rupees = {'Rupee (1)': 1, 'Rupees (5)': 5, 'Rupees (20)': 20, 'Rupees (50)': 50, 'Rupees (100)': 100, 'Rupees (300)': 300}
    if name in rupees:
        cur = await snes_read(ctx, SAVEDATA_START + 0x360, 2)
        if cur is None:
            return
        target_rupees = (cur[0] + (cur[1] * 0x100)) + rupees[name]
        await snes_write(ctx, SAVEDATA_START + 0x360, bytes([target_rupees & 0xFF, (target_rupees >> 8) & 0xFF]))
        return

    bottles = {'Bottle': 2, 'Bottle (Red Potion)': 3, 'Bottle (Green Potion)': 4, 'Bottle (Blue Potion)': 5, 'Bottle (Fairy)': 6, 'Bottle (Bee)': 7, 'Bottle (Good Bee)': 8}
    if name in bottles:
        cur = await snes_read(ctx, SAVEDATA_START + 0x35C, 4)
        if cur is None:
            return
        buf = list(cur)
        for i in range(4):
            if buf[i] == 0:
                buf[i] = bottles[name]
                break
        await snes_write(ctx, SAVEDATA_START + 0x35C, bytes(buf))
        return

    simple_items = {'Hookshot': (0x342, 0x01), 'Fire Rod': (0x345, 0x01), 'Ice Rod': (0x346, 0x01),
                    'Bombos': (0x347, 0x01), 'Ether': (0x348, 0x01), 'Quake': (0x349, 0x01),
                    'Lamp': (0x34A, 0x01), 'Hammer': (0x34B, 0x01), 'Bug Catching Net': (0x34D, 0x01), 'Book of Mudora': (0x34E, 0x01),
                    'Cane of Somaria': (0x350, 0x01), 'Cane of Byrna': (0x351, 0x01),'Cape': (0x352, 0x01),
                    'Magic Mirror': (0x353, 0x02), 'Flippers': (0x356, 0x01), 'Moon Pearl': (0x357, 0x01),
                    'Single Arrow': (0x376, 0x01), 'Arrows (10)': (0x376, 0x0A),
                    'Single Bomb': (0x375, 0x01), 'Bombs (3)': (0x375, 0x03), 'Bombs (10)': (0x375, 0x0A)}
    if name in simple_items:
        await snes_write(ctx, SAVEDATA_START + simple_items[name][0], bytes([simple_items[name][1]]))
        return

    if name == 'Pegasus Boots':
        cur = await snes_read(ctx, SAVEDATA_START + 0x379, 1)
        if cur is None:
            return
        dash_flag = cur[0] | 0x04
        await snes_write(ctx, SAVEDATA_START + 0x379, bytes([dash_flag]))
        await snes_write(ctx, SAVEDATA_START + 0x355, bytes([0x01]))
        return

    if name == 'Progressive Glove':
        cur = await snes_read(ctx, SAVEDATA_START + 0x354, 1)
        if cur is None:
            return
        gloves = cur[0] + 1
        if gloves <= 2:
            await snes_write(ctx, SAVEDATA_START + 0x354, bytes([gloves]))
        return

    if name == 'Progressive Sword':
        cur = await snes_read(ctx, SAVEDATA_START + 0x359, 1)
        if cur is None:
            return
        swords = cur[0] + 1
        if swords <= 4:
            await snes_write(ctx, SAVEDATA_START + 0x359, bytes([swords]))
        return

    if name == 'Progressive Shield':
        cur = await snes_read(ctx, SAVEDATA_START + 0x416, 1)
        if cur is None:
            return
        shields = cur[0] + 1
        if shields <= 3:
            await snes_write(ctx, SAVEDATA_START + 0x416, bytes([shields]))
            await snes_write(ctx, SAVEDATA_START + 0x35A, bytes([shields]))
        return

    if name == 'Progressive Armor':
        cur = await snes_read(ctx, SAVEDATA_START + 0x35B, 1)
        if cur is None:
            return
        armors = cur[0] + 1
        if armors <= 2:
            await snes_write(ctx, SAVEDATA_START + 0x35B, bytes([armors]))
        return

    async def increase_hearts(refill): # 8 is one heart refill, 1 is full
        cur = await snes_read(ctx, SAVEDATA_START + 0x36C, 1)
        if cur is None:
            return
        hearts = min(cur[0] + 8, 20 * 8)
        if hearts != cur[0]:
            await snes_write(ctx, SAVEDATA_START + 0x36C, bytes([hearts]))
        if refill:
            await snes_write(ctx, SAVEDATA_START + 0x372, bytes([refill]))

    if name == 'Boss Heart Container':
        await increase_hearts(0x08)
        return

    if name == 'Sanctuary Heart Container':
        await increase_hearts(0x01)
        return

    if name == 'Piece of Heart':
        cur = await snes_read(ctx, SAVEDATA_START + 0x36B, 1)
        if cur is None:
            return
        pieces = cur[0] + 1
        if pieces >= 4:
            pieces = 0
            await increase_hearts(0x01)
        await snes_write(ctx, SAVEDATA_START + 0x36B, bytes([pieces]))
        return

    print('Unknown item: ' + name)

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

    input_task = asyncio.create_task(console(ctx))

    await snes_connect(ctx)

    asyncio.create_task(game_watcher(ctx))

    if ctx.server_task is None:
        ctx.server_task = asyncio.create_task(server_loop(ctx))

    await input_task

class ReceivedItem:
    def __init__(self, name, location, player_id, player_name):
        self.name = name
        self.location = location
        self.player_id = player_id
        self.player_name = player_name

class Context:
    def __init__(self, snes_address, server_address, password, name, team, slot):
        self.snes_address = snes_address
        self.server_address = server_address

        self.input_queue = asyncio.Queue()
        self.input_requests = 0

        self.snes_socket = None
        self.snes_state = SNES_DISCONNECTED
        self.snes_recv_queue = asyncio.Queue()
        self.snes_request_queue = None

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

if __name__ == '__main__':
    asyncio.run(main())
