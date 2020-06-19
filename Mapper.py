import graphviz
from collections import defaultdict, deque
from graphviz import Digraph, Graph
from DungeonGenerator import convert_regions
from BaseClasses import RegionType, Door, DoorType, Direction, Sector, CrystalBarrier, Direction, Region
from DoorShuffle import interior_doors, logical_connections, dungeon_warps, switch_dir_safe
from MapData import region_to_rooms, make_room


def get_door_port(region, door, is_lead):
    def f(door, is_lead):
        if door:
            if type(door) != Door:
                return ''

            if door.type == DoorType.Warp:
                return 'c'
            elif door.type == DoorType.Hole:
                if is_lead:
                    return 's'
                return 'n'
            port_mapping = {
                Direction.West : 'w',
                Direction.East : 'e',
                Direction.South : 's',
                Direction.North : 'n',
                #Direction.Up : ':n',  # Allow any direction, these are stairs...
                #Direction.Down : ':s',
            }

            if door.direction in port_mapping:
                return port_mapping[door.direction]

        # probably fall?
        return 'n'
    d = f(door, is_lead)

    if d:
        d = ":" + region.name + '_' + d
    return d


def generate_connection(region_to_horiz_region, graph, region, connect, door_a, door_b):
    arrow_dir = 'forward'
    if type(door_b) == Door:
        if not door_b.blocked and not door_a.blocked:
            arrow_dir = 'both'
        elif door_a.blocked:
            arrow_dir = 'back'
    else:
        #print(f"Warning {door_b} is not a door")
        pass
    

    name_a = region_to_horiz_region[region][0].name + get_door_port(region, door_a, True)
    name_b = region_to_horiz_region[connect][0].name + get_door_port(connect, door_b, False)

    constraint_types = [
        DoorType.Normal,
        DoorType.StraightStairs,
        DoorType.Hole,
        DoorType.Interior,
        DoorType.Open,
    ]
    constraint= 'true' if door_a.type in constraint_types else 'false'

    spline = 'polyline' if door_a.type == DoorType.SpiralStairs or door_a.type == DoorType.Warp else 'spline'

    if door_a.direction == Direction.East or door_a.direction == Direction.West:
        assert(constraint)

    # fix horizontal order
    if door_a.direction == Direction.West or  door_a.direction == Direction.South or door_a.type == DoorType.Hole:
        if arrow_dir == 'forward':
            arrow_dir = 'back'
        elif arrow_dir == 'back':
            arrow_dir = 'forward'
        graph.edge(name_b, name_a, dir=arrow_dir,constraint=constraint, splines=spline)
    else:
        graph.edge(name_a, name_b, dir=arrow_dir,constraint=constraint,splines=spline)
cluster_index = 0

def is_valid_map_exit(exit):
    return exit.door and get_region(exit) and get_region(exit).type == RegionType.Dungeon

def opposite_ew_dir(direction):
    if direction == Direction.East:
        return Direction.East
    elif direction == Direction.West:
        return Direction.West
    assert(False)

def get_valid_single_dirs(region, noisy=False):
    num_exits_dir = {}
    found_exits_dir = {}
    for exit in region.exits:
        if not is_valid_map_exit(exit):
            if noisy:
                print("Skipped " + str(exit.door.name) + " not valid")
            continue

        # allowed to loop on self
        if get_region(exit) == region:
            if noisy:
                print("Skipped " + str(exit.door.name) + " self loop")
            continue

        direction = exit.door.direction

        #defaultdict

        # allowed multiple arrows to the same place
        if direction not in found_exits_dir or found_exits_dir[direction] != get_region(exit):
            if noisy:
                print("Added " + str(exit.door.name) + " on " + str(direction))
            num_exits_dir.setdefault(direction, 0)
            num_exits_dir[direction] += 1
            #if num_exits_dir[direction] > 1:
            #    print("invalid dir!")
            found_exits_dir.setdefault(direction, []).append(get_region(exit))
        else:
            print("Skipped " + str(exit.door.name) + " " + str(direction) + " " + str(found_exits_dir.get(direction)))


    assert (num_exits_dir.get(Direction.West, 0) == len(found_exits_dir.get(Direction.West, [])))
    assert (num_exits_dir.get(Direction.East, 0) == len(found_exits_dir.get(Direction.East, [])))

    found_entrances_dir = {}

    for entrance in region.entrances:
        if is_valid_map_exit(entrance):
            if entrance.parent_region != region:
                direction = switch_dir_safe(entrance.door.direction)
                if direction:
                    found_entrances_dir.setdefault(direction, []).append(entrance.parent_region)

    #return set(d for d in num_exits_dir if num_exits_dir[d] == 1)
    # 

    dirs = [Direction.West, Direction.East]

    def ok(d):
        if len(found_exits_dir.get(d, [])) > 1:
            return False
        if len(found_entrances_dir.get(d, [])) > 1:
            return False

        total = len(found_exits_dir.get(d, [])) + len(found_entrances_dir.get(d, []))
        if total == 0:
            return False
        if total == 1:
            return True
        if total == 2:
            return found_exits_dir[d][0] == found_entrances_dir[d][0]

    return {
                d:(found_exits_dir.get(d) or found_entrances_dir.get(d))[0] for d in dirs 
                if ok(d)            }

logical_regions = set()

LOGICAL_INTERIOR_DOORS = True
def generate_logical_regions():
    #assert(not logical_regions)
    global logical_regions

    for connection in logical_connections+(interior_doors if LOGICAL_INTERIOR_DOORS else []):
        logical_regions.add(connection[0])
        logical_regions.add(connection[1])

    # Fixup GT warp maze D:
    for connection in dungeon_warps:
        if 'GT Warp Maze' in connection[0]:
            logical_regions.add(connection[0])
            logical_regions.add(connection[1])

    # TODO: convert lists into logical name

def get_region(exit):
    return exit.connected_region

from copy import copy

def merge_regions(a, b):
    # don't merge regions in the REAL world
    assert(a.world is None)
    assert(b.world is None)
    
    for exit in b.exits:
        other_region = exit.connected_region
        if other_region != a:
            # find all the exits and replace references
            # probably could just loop over the entrances instead...
            # ...would require validation and setting up the entrances    
            
            for other_exit in other_region.exits:
                if other_exit.connected_region == b:
                    other_exit.connected_region = a
        a.exits.append(exit)

    a.exits = [exit for exit in a.exits if exit.connected_region != b]
    a.exits = [exit for exit in a.exits if (exit.connected_region != a) or (exit.name not in logical_regions)]
    # clear the exits so we don't try to use them
    b.exits = []

                    

# TODO: all of this is leaving a bunch of properties pointing to the real world. TAKE CARE.
# doing this needs a LOT of memoization
def copy_exit(exit, region):
    out = copy(exit)
    out.parent_region = region
    #out.door = copy(exit.door)
    return out

def generate_shadow_region(region):
    shadow_region = Region(region.name, region.type, 'this is a bug - you are in the shadow realm', region.player)
    shadow_region.exits = [copy_exit(exit, shadow_region) for exit in region.exits if is_valid_map_exit(exit)]

    return shadow_region

def regenerate_entrances_from_exits(regions):
    for region in regions:
        region.entrances = []

    for region in regions:
        for exit in region.exits:
            exit.connected_region.entrances.append(exit)

def generate_shadow_dungeon(start_regions):
    reg_queue = deque(start_regions)
    visited = set(start_regions)

    shadow_dungeon = []
    shadow_start_regions = set()

    region_to_shadow_region = {None: None}

    # Walk the dungeon graph
    while len(reg_queue) > 0:
        region = reg_queue.pop()
        
        # Make a copy of the region
        shadow_region = generate_shadow_region(region)
        shadow_dungeon.append(shadow_region)
        region_to_shadow_region[region] = shadow_region

        if region in start_regions:
            shadow_start_regions.add(shadow_region)

        # walk all exits that don't go outside
        for exit in region.exits:
            if not is_valid_map_exit(exit):
                continue

            if exit.connected_region and exit.connected_region not in visited:
                visited.add(exit.connected_region)
                reg_queue.append(exit.connected_region)

    # fixup exit references - they were copied but still refer to the real dungeon
    for shadow_region in shadow_dungeon:
        for exit in shadow_region.exits:
            exit.connected_region = region_to_shadow_region[exit.connected_region]

    regenerate_entrances_from_exits(shadow_dungeon)

    return shadow_dungeon, shadow_start_regions
    # TODO: handle entrances



TABLE_START = "<<TABLE BORDER=\"0\" CELLBORDER=\"0\" CELLSPACING=\"0\" CELLPADDING=\"0\" >"
ROW_START = "<TR>"
CELL_FORMAT = "<TD{port}>{image}{label}</TD>"
ROW_END = "</TR>"
TABLE_END = "</TABLE>>"

def make_cell(label="", image='', port=""):
    if port:
        port = " HEIGHT=\"{}\" WIDTH=\"{}\" PORT=\"{}\"".format(100 if label else 0, 100 if label else 0, port)
    if image:
        image = f'<IMG SRC="{image}" />'
    return CELL_FORMAT.format(label=label, port=port, image=image)#image if label else '')

table_index = 0


def get_room_image(region):
    #return region_to_rooms.get(region.name, region_to_rooms[region.name[1:]])

    #return region_to_rooms.get(region.name)
    return merged_room_data.get(region.name)

from collections import defaultdict

def add_offset(p, o):
    return (p[0] + o[0], p[1] + o[1])

quad_to_offset = [
    (0,0),
    (1,0),
    (0,1),
    (1,1),
]





class RoomGrid():
    def __init__(self):
        #self.extents = [[0,0],[0,0]]
        self.last_room = None
        self.grid = {}#defaultdict(str)

    def _extents_for_grid(self,grid):
        if not grid:
            return ((0,0),(0,0))
        min_x = 1000
        min_y = 1000
        max_x = -1000
        max_y = -1000
        for x,y in grid:
            min_x = min(x, min_x)
            min_y = min(y, min_y)
            max_x = max(x, max_x)
            max_y = max(y, max_y)
        return ((min_x, min_y), (max_x, max_y))

    # this is a mess
    def add_region(self, region):
        supertile = get_room_image(region)
        if not supertile:
            return
        
        base_addr = (0,0)
        # always add to upper right for now

        if self.grid:
            extents = self._extents_for_grid(self.grid)
            base_addr = (extents[1][0] + 1, extents[0][1])
        
        

        supertile_grid = supertile_to_grid(supertile)
        print(region.name)
        print(supertile_grid)
        print(self.grid)
        print(f'BA: {base_addr}')
        for y in range(len(supertile_grid)):
            row = supertile_grid[y]
            for x in range(len(row)):
                if row[x]:
                    # don't allow overwrite
                    assert not self.grid.get(add_offset(base_addr, (x, y)))

                    self.grid[add_offset(base_addr, (x, y))] = row[x]


            #addr = add_offset(addr, )


# take the quadrants, if there's no 
def supertile_to_grid(supertile):
    return supertile
    # this is crazy, we really just need to get the extents of the supertile, why did i write it this way??!
    # TODO: let RoomData generate this
    # TODO: didn't I do this already?!
    grid = [[None, None], [None, None]]
    print('grid')
    for quad in supertile[1]:
        offset = quad_to_offset[quad]
        grid[offset[1]][offset[0]] = (supertile[0], quad)
    print(grid)
    if not grid[0][0] and not grid[1][0]:
        print("remove col")
        grid = [[grid[0][1]], [grid[1][1]]]
        print(grid)
    elif not grid[0][1] and not grid[1][1]:
        print("remove col")
        grid = [[grid[0][0]], [grid[1][0]]]
        print(grid)
    for y in range(0, 1):
        row = grid[y]
        if all(x is None for x in row):
            print("remove row")
            grid = [grid[1 - y]]
            print(grid)
            break

    return grid
    
#    rooms = set()
#    for exit in region.exits:
#        if exit.door.roomIndex != -1:
#            rooms.add((exit.door.roomIndex, exit.door.quadrant))

#    return list(rooms)

def get_y_size(room):
    # TODO have to handle different doors _eventually_

    #quads = [supertile[1] for supertile in room]

    quads = supertile[1]

    if 0 in quads and 2 in quads:
        return 2
    if 1 in quads and 3 in quads:
        return 2

    return 1

def get_x_size(room):
    quads = supertile[1]

    if 0 in quads and 1 in quads:
        return 2
    if 2 in quads and 3 in quads:
        return 2

    return 1

def construct_geometry_for_group(group):
    # this is sort of overdone
    RG = RoomGrid()

    for region in group:
        RG.add_region(region)

    return RG
def make_table_for_group(graph, group):
    room_grid = construct_geometry_for_group(group)


    global table_index
    #dungeon_subgraph.node(region.name, shape='circle' if region in start_regions else 'box')
    # 
    s = TABLE_START

    s += ROW_START
    s += make_cell() 
    for region in group:
        s += make_cell(port=region.name+'_n')
    s += make_cell() 
    s += ROW_END


    extents = room_grid._extents_for_grid(room_grid.grid)



    for y in range(extents[0][1], extents[1][1]+1):

        s += ROW_START
        s += make_cell(port=group[0].name+'_w') 

        for x in range(extents[0][0], extents[1][0]+1):
            tile = room_grid.grid.get((x, y))

            image=''
            label = 'not found'
            if tile:
                image = f'room_images/{tile[0]}-{tile[1]}.png'
                label = ''
            s += make_cell(label, port=region.name, image =image)
        s += make_cell(port=group[-1].name+'_e') 
        s += ROW_END

    s += ROW_START
    s += make_cell() 
    for region in group:
        
        image = ''
        label = region.name 
        s += make_cell(label, port=region.name, image =image)
    s += make_cell() 
    s += ROW_END

    s += ROW_START
    s += make_cell() 
    for region in group:
        s += make_cell(port=region.name+'_s')
    s += make_cell() 
    s += ROW_END

    s += TABLE_END

#    graph.node(s, shape='circle' if group[0] in start_regions else 'box')
    graph.node(group[0].name,label=s, shape='box')
    table_index += 1

def add_region_group(graph, group):
    #for region in group:
    #    make_table_for_group(graph, [region])
    make_table_for_group(graph, group)

# uuuugh globals. TODO: wrap html generation into class to allow passing context
merged_room_data = {}
def map(world):
    global merged_room_data

    player = 1

    queue = deque(world.dungeon_layouts[player].values())

    # TODO: pass player here and reset

    graph = Digraph(comment='Maps',  graph_attr={'rankdir': 'BT'}, node_attr={'shape': 'box'})

    generate_logical_regions()

    while len(queue) > 0:
        builder = queue.popleft()
        done = set()

        start_regions = set(convert_regions(builder.layout_starts, world, player))  # todo: set all_entrances for basic

        shadow_dungeon, start_regions = generate_shadow_dungeon(start_regions)

        dead_regions = set()

        def get_room_data(region):
            if region in merged_room_data:
                return merged_room_data[region]
            return 

        def supertile_for_room(room):
            for row in room:
                for tile in row:
                    if tile:
                        return tile[0]

        def fixup_exit(region, merged_region):
            # hackery because I didn't copy entrances TODO fix this

            for region2 in shadow_dungeon:
                for exit in region2.exits:
                    #assert(exit.connected_region not in dead_regions)
                    if exit.connected_region == merged_region:
                        exit.connected_region = region

        merged_room_data = copy(region_to_rooms)
        for name in merged_room_data:
            if not merged_room_data[name]:
                merged_room_data[name] = [ [ [0,0] ] ]

        supertile_to_region = {}
        for region in shadow_dungeon:
            assert(region.name in merged_room_data)
            room = merged_room_data[region.name]
            if room:
                supertile_to_region.setdefault(supertile_for_room(room), []).append((region, room))

        def overlapping_rooms(a, b):
            quad_a = []
            print(a)
            for row in a:
                for p in row:
                    if not p:
                        continue
                    i, q = p
                    quad_a.append(q)

            quad_b = []
            for row in b:
                for p in row:
                    if not p:
                        continue
                    i, q = p
                    quad_b.append(q)
            for q in quad_a:
                if q in quad_b:
                    return True

            return False

        def merge_rooms(a, b):
            quads = set()
            for row in a:
                for p in row:
                    if not p:
                        continue
                    i, q = p
                    quads.add(q)

            
            for row in b:
                for p in row:
                    if not p:
                        continue
                    i, q = p
                    quads.add(q)
            
            return make_room(supertile_for_room(a), list(quads))

        MERGE_BY_ROOM_DATA = True
        if MERGE_BY_ROOM_DATA:
            for supertile_key in supertile_to_region:
                if supertile_key == 0:
                    continue
                supertile = supertile_to_region[supertile_key]
                while True:
                    merged_some_rooms = False
                    for region, room in supertile:

                        merged_some_rooms = False
                        for other_region, other_room in supertile:
                            if region == other_region:
                                continue

                            # TODO: check for logical connection + interior door here
                            should_merge = overlapping_rooms(room, other_room)

                            if not should_merge:
                                for exit in region.exits:
                                    if exit.name in logical_regions:
                                        if exit.connected_region == other_region:
                                            should_merge = True


                            if should_merge:
                                merge_regions(region, other_region)
                                dead_regions.add(other_region)
                                fixup_exit(region, other_region)
                                print(f'merging {region.name} + {other_region.name}')
                                print(f'merging {room} + {other_room}')
                                new_room = merge_rooms(room, other_room)
                                print(new_room)
                                merged_room_data[region.name] = new_room
                                supertile = [p for p in supertile if p[0] != other_region and p[0] != region] + [(region, new_room)]
                                merged_some_rooms = True
                                break
                            else:
                                print(f'not merging {region.name} + {other_region.name}')
                                print(f'not merging {room} + {other_room}')

                        if merged_some_rooms:
                            break
                    if not merged_some_rooms:
                        break

        #while True:
        #    did_logical_merge
        # uuuuugh
        regenerate_entrances_from_exits(shadow_dungeon)


        MERGE_LOGICAL_REGIONS = False
        if MERGE_LOGICAL_REGIONS:
            for region in shadow_dungeon:
                if region in dead_regions:
                    continue
                while True:
                    for exit in region.exits:
                        if exit.name in logical_regions:
                            if exit.connected_region != region:
                                print(f"Merge {region.name} <- {exit.connected_region.name}")
                                merge_regions(region, exit.connected_region)
                                dead_regions.add(exit.connected_region)
                                fixup_exit(region, exit.connected_region)
                                
                                # restart the search, we got more exits
                                break
                    else:
                        # we didn't hit any logical reasons, now we can stop
                        break

        shadow_dungeon = [region for region in shadow_dungeon if region not in dead_regions]


        # TODO  outputorder=nodesfirst
        future_connections = {}



        with graph.subgraph(name='cluster_'+str(builder)) as dungeon_subgraph:

            # todo: just rewrite all this crap
            horiz_regions = []
            region_to_horiz_region = {}

            walked_regions = set()

            def new_horiz_region(region):
                horiz_regions.append([region])
                region_to_horiz_region[region] = horiz_regions[-1]

            # Once we are more knowledgable about door locations and dungeon shapes we can use a fitting algo to allow for N/S stuff too
            def process_region(region, cur_list=[]):
                if region in walked_regions:
                    return cur_list
                print("walking to " + region.name)
                walked_regions.add(region)

                valid_single_dirs = get_valid_single_dirs(region, True)


                if Direction.West in valid_single_dirs and valid_single_dirs[Direction.West] not in cur_list:
                    west_region = valid_single_dirs[Direction.West]
                    
                    cur_list = process_region(west_region, cur_list + [region])

                    valid_single_dirs_for_west = get_valid_single_dirs(west_region)
      

                    if valid_single_dirs_for_west.get(Direction.East) == region:
                        # TODO: this can fail...how?!
                        print("link " + region.name + " is east of " + west_region.name) 
                        h_region = region_to_horiz_region[west_region]

                        h_region.append(region)
                        region_to_horiz_region[region] = h_region
                    else:
                        foobar = valid_single_dirs_for_west.get(Direction.East)
                        if foobar:
                            print("Pointed to " + foobar.name)
                        else:
                            print("Pointed to none")

                        # Our valid west region has a oneway to somewhere else, make a new region
                        new_horiz_region(region)    
                else:
                    # we are by definition the westmost region, start a new horiz region
                    new_horiz_region(region)

                # attempt to walk east...this doesn't work well
                # really we need to split exit processing and combining ffs
                assert valid_single_dirs is not None
                if Direction.East in valid_single_dirs and valid_single_dirs[Direction.East] not in cur_list:
                    
                    
                    process_region(valid_single_dirs[Direction.East], cur_list)

                for exit in region.exits:
                    if not is_valid_map_exit(exit):
                        continue
                    door_a = exit.door
                    
                    connect = get_region(exit)
               
                    door_b = door_a.dest
                    assert(door_b)
                    if door_a not in done:
                        done.add(door_a)
                        # TODO: this is really dumb - we should just check if we are walking through a link that's in our horiz region :(
                        if (door_a.direction == Direction.West or door_a.direction == Direction.East) and door_a.direction in valid_single_dirs:

                            if get_valid_single_dirs(valid_single_dirs[door_a.direction]).get(opposite_ew_dir(door_a.direction), None) == region:
                                pass
                            elif door_b not in done:
                                future_connections.setdefault(region, []).append((region, connect, door_a, door_b))
                                pass
                        else:
                            if door_b not in done:
                                #generate_connection(dungeon_subgraph, region, connect, door_a, door_b)
                                future_connections.setdefault(region, []).append((region, connect, door_a, door_b))

                return cur_list
            for region in shadow_dungeon:


                process_region(region)

            print(len(future_connections))
            # for horiz_region in horiz_regions:
            #     global cluster_index
            #     with dungeon_subgraph.subgraph(name='cluster_'+str(cluster_index)) as cluster:
            #         #cluster.attr(style='invis')
            #         cluster_index += 1
            #         with cluster.subgraph() as subregion:
            #             subregion.attr(rank='same')

            #             for region in horiz_region:
                       
            #                 for c in future_connections.get(region, []):
            #                     generate_connection(subregion, c[0], c[1], c[2], c[3])



            for horiz_region in horiz_regions:

                add_region_group(dungeon_subgraph, horiz_region)

            for horiz_region in horiz_regions:
                for region in horiz_region:
                    for c in future_connections.get(region, []):
                        generate_connection(region_to_horiz_region, dungeon_subgraph, c[0], c[1], c[2], c[3])
                        
    graph.render('test-output/map.gv', view=True) 
    
