import graphviz
from collections import defaultdict, deque
from graphviz import Digraph, Graph
from DungeonGenerator import convert_regions
from BaseClasses import RegionType, Door, DoorType, Direction, Sector, CrystalBarrier, Direction


def get_door_port(door):
    if door:
        if type(door) != Door:
            return ''
        port_mapping = {
            Direction.West : ':w',
            Direction.East : ':e',
            Direction.South : ':s',
            Direction.North : ':n',
            Direction.Up : ':n',  # ????
            Direction.Down : ':n',
        }

        if door.direction in port_mapping:
            return port_mapping[door.direction]
    return ''
def map(world):
    player = 1
    queue = deque(world.dungeon_layouts[player].values())

    graph = Digraph(comment='Maps',  graph_attr={'rankdir': 'BT'}, node_attr={'shape': 'box'})

    while len(queue) > 0:
        builder = queue.popleft()
        done = set()
        start_regions = set(convert_regions(builder.layout_starts, world, player))  # todo: set all_entrances for basic
        reg_queue = deque(start_regions)
        visited = set(start_regions)
        # TODO 

        print(builder.name)
        with graph.subgraph(name='cluster_'+str(builder)) as dungeon_subgraph:

            graph_regions = []

            horiz_regions = []
            region_to_horiz_region = {}
            while len(reg_queue) > 0:
                region = reg_queue.pop()
                
                graph_regions.append(region)

                prospective_horiz_regions = []

                for ext in region.exits:
                    door_a = ext.door
                    
                    connect = ext.connected_region
                   
                    if connect:
                        if 'World' not in connect.name:
                            if door_a:
                                door_b = door_a.dest
                                assert(door_b)
                                if door_a not in done:
                                    done.add(door_a)
                                    #, constraint='false' if door_a.direction == Direction.West or door_a.direction == Direction.East else 'true'
                                    if door_b not in done:
                                        arrow_dir = 'forward'
                                        if type(door_b) == Door:
                                            if not door_b.blocked and not door_a.blocked:
                                                arrow_dir = 'both'
                                            elif door_b.blocked:
                                                arrow_dir = 'back'
                                        else:
                                            print(f"Warning {door_b} is not a door")
                                        name_a = region.name + get_door_port(door_a)
                                        name_b = connect.name + get_door_port(door_b)
                                        # fix horizontal order
                                        if door_a.direction == Direction.West or  door_a.direction == Direction.South:
                                            if arrow_dir == 'forward':
                                                arrow_dir = 'back'
                                            elif arrow_dir == 'back':
                                                arrow_dir = 'forward'
                                            dungeon_subgraph.edge(name_b, name_a, dir=arrow_dir)
                                        else:
                                            dungeon_subgraph.edge(name_a, name_b, dir=arrow_dir)
                                    if door_a.direction == Direction.West or door_a.direction == Direction.East:
                                        if connect in region_to_horiz_region:
                                            subregion = region_to_horiz_region[connect]
                                            if subregion not in prospective_horiz_regions:
                                                prospective_horiz_regions.append(subregion)
                                    
                                    



                    if connect and connect.type == RegionType.Dungeon and connect not in visited:
                        visited.add(connect)
                        reg_queue.append(connect)
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
                
            for horiz_region in horiz_regions:
                with dungeon_subgraph.subgraph() as subregion:
                    subregion.attr(rank='same')
                    # sort the regions so that they appear in the right order

                    


                    touched_regions = []

                    region = horiz_region[0]
                    # make do-while...?
                    no_left = False
                    while True:
                        touched_regions.append(region)
                        for ext in region.exits:
                            door_a = ext.door
                            if door_a and door_a.direction == Direction.East and ext.connected_region in horiz_region:
                                if ext.connected_region not in touched_regions:
                                    region = ext.connected_region
                                    break

                        else:
                            break
                    
                    sorted_regions = []

                    while True:
                        sorted_regions.append(region)
                        for ext in region.exits:
                            door_a = ext.door
                            if door_a and door_a.direction == Direction.West and ext.connected_region in horiz_region:
                                if ext.connected_region not in sorted_regions:
                                    region = ext.connected_region
                                    break
                        else:
                            break
                    #assert(len(sorted_regions) == len(horiz_region))
                    print(len(sorted_regions))

                    #for region in horiz_region:
                    #    for ext in region.exits:
                    #        door_a = ext.door
                    #        connect = ext.connected_region
                    #        door_b = door_a.dest
                                
                                #, constraint='false' if door_a.direction == Direction.West or door_a.direction == Direction.East else 'true'
                    #        if door_a.direction == Direction.West or door_a.direction == Direction.East:
                    for region in horiz_region:
                        subregion.node(region.name, shape='circle' if region in start_regions else 'box')
    graph.render('test-output/map.gv', view=True) 
    
