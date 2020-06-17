import graphviz
from collections import defaultdict, deque
from graphviz import Digraph, Graph
from DungeonGenerator import convert_regions
from BaseClasses import RegionType, Door, DoorType, Direction, Sector, CrystalBarrier, Direction, Region
from DoorShuffle import interior_doors, logical_connections, dungeon_warps
def t():
    dot = Digraph(comment='The Round Table')

    dot.node('A', 'King Arthur')
    dot.node('B', 'Sir Bedevere the Wise')
    dot.node('L', 'Sir Lancelot the Brave')

    dot.edges(['AB', 'AL'])
    dot.edge('B', 'L', constraint='false')
    print(dot.source)
    dot.render('test-output/round-table.gv', view=True)


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


def generate_connection(graph, region, connect, door_a, door_b):
    arrow_dir = 'forward'
    if type(door_b) == Door:
        if not door_b.blocked and not door_a.blocked:
            arrow_dir = 'both'
        elif door_a.blocked:
            arrow_dir = 'back'
    else:
        #print(f"Warning {door_b} is not a door")
        pass
    name_a = region.name + get_door_port(region, door_a, True)
    name_b = connect.name + get_door_port(connect, door_b, False)

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

def is_valid_map_exit(ext):
    return ext.door and get_region(ext) and get_region(ext).type == RegionType.Dungeon

def opposite_ew_dir(dir):
    if direction == Direction.East:
        return Direction.East
    elif direction == Direction.West:
        return Direction.West
    assert(False)

def get_valid_single_dirs(region):
    num_exits_dir = {}
    found_exits_dir = {}
    for exit in region.exits:
        if not is_valid_map_exit(exit):
            continue

        # allowed to loop on self
        if get_region(exit) == region:
            continue

        direction = exit.door.direction

        #defaultdict

        # allowed multiple arrows to the same place
        if direction not in found_exits_dir or found_exits_dir[direction] != get_region(exit):
            num_exits_dir.setdefault(direction, 0)
            num_exits_dir[direction] += 1
            #if num_exits_dir[direction] > 1:
            #    print("invalid dir!")
            found_exits_dir[direction] = get_region(exit)

    return set(d for d in num_exits_dir if num_exits_dir[d] == 1)

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

def get_region(ext):
    return ext.connected_region

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

    # temp
    if a.name[0] != '*':
        a.name = '*' + a.name
                    


def generate_shadow_region(region):
    shadow_region = Region(region.name, region.type, 'this is a bug - you are in the shadow realm', region.player)
    shadow_region.exits = [copy(exit) for exit in region.exits if is_valid_map_exit(exit)]

    return shadow_region

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

    return shadow_dungeon, shadow_start_regions
    # TODO: handle entrances



TABLE_START = "<<TABLE BORDER=\"0\" CELLBORDER=\"0\" CELLSPACING=\"0\" CELLPADDING=\"0\" >"
ROW_START = "<TR>"
CELL_FORMAT = "<TD{port}>{label}</TD>"
ROW_END = "</TR>"
TABLE_END = "</TABLE>>"

def make_cell(label="", port=""):
    if port:
        port = " PORT=\"{}\"".format(port)
    return CELL_FORMAT.format(label=label, port=port)

table_index = 0

def make_table_for_group(graph, group):
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

    s += ROW_START
    s += make_cell(port=group[0].name+'_w') 
    for region in group:
        s += make_cell(region.name, port=region.name)
    s += make_cell(port=group[0].name+'_e') 
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
    for region in group:
        make_table_for_group(graph, [region])

def map(world):
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
        for region in shadow_dungeon:
            while True:
                for exit in region.exits:
                    if exit.name in logical_regions:
                        if exit.connected_region != region:
                            print(f"Merge {region.name} <- {exit.connected_region.name}")
                            merge_regions(region, exit.connected_region)
                            dead_regions.add(exit.connected_region)
                            # restart the search, we got more exits
                            break
                else:
                    # we didn't hit any logical reasons, now we can stop
                    break

        shadow_dungeon = [region for region in shadow_dungeon if region not in dead_regions]
        # TODO  outputorder=nodesfirst
        future_connections = {}


        with graph.subgraph(name='cluster_'+str(builder)) as dungeon_subgraph:


            horiz_regions = []
            region_to_horiz_region = {}
            for region in shadow_dungeon:


                prospective_horiz_regions = []

                valid_single_dirs = get_valid_single_dirs(region)


                for ext in region.exits:
                    if not is_valid_map_exit(ext):
                        continue
                    door_a = ext.door
                    
                    connect = get_region(ext)
               
                    door_b = door_a.dest
                    assert(door_b)
                    if door_a not in done:
                        done.add(door_a)
                        
                        if (door_a.direction == Direction.West or door_a.direction == Direction.East) and door_a.direction in valid_single_dirs:
                            if connect in region_to_horiz_region:
                                subregion = region_to_horiz_region[connect]
                                if subregion not in prospective_horiz_regions:
                                    prospective_horiz_regions.append(subregion)
                            if door_b not in done:
                                future_connections.setdefault(region, []).append((region, connect, door_a, door_b))
                                #print('added future connection' + str(region.name))
                        else:
                            if door_b not in done:
                                generate_connection(dungeon_subgraph, region, connect, door_a, door_b)
                        
         
                        
                prospective_horiz_regions = list(prospective_horiz_regions)
                # This door didn't find any other already linked east or west locations
                # Let's be the first
                if not prospective_horiz_regions:
                    region_to_horiz_region[region] = [region]
                    horiz_regions.append(region_to_horiz_region[region])
                else:
                    while len(prospective_horiz_regions) > 1:
                        print("Reducing subregions to " + str( len(prospective_horiz_regions) ))
                        for moving_region in prospective_horiz_regions[-1]:
                            print(f"move {moving_region}")
                            print(len(prospective_horiz_regions[-1]))
                            print(len(prospective_horiz_regions[0]))
                            prospective_horiz_regions[0].append(moving_region)
                            region_to_horiz_region[moving_region] = prospective_horiz_regions[0]
                        horiz_regions.remove(prospective_horiz_regions[-1])
                        prospective_horiz_regions = prospective_horiz_regions[:-1]
                    prospective_horiz_regions[0].append(region)
                    region_to_horiz_region[region] = prospective_horiz_regions[0]
            print(len(future_connections))
            for horiz_region in horiz_regions:
                global cluster_index
                with dungeon_subgraph.subgraph(name='cluster_'+str(cluster_index)) as cluster:
                    #cluster.attr(style='invis')
                    cluster_index += 1
                    with cluster.subgraph() as subregion:
                        subregion.attr(rank='same')

                        for region in horiz_region:
                       
                            for c in future_connections.get(region, []):
                                generate_connection(subregion, c[0], c[1], c[2], c[3])
            for horiz_region in horiz_regions:
                add_region_group(dungeon_subgraph, horiz_region)
                        
    graph.render('test-output/map.gv', view=True) 
    
