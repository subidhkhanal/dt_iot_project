"""
Generate SUMO vehicle routes for IoV simulation.
Run this after building the network with netconvert.
"""
import random
import xml.etree.ElementTree as ET
import os

# All edge IDs from our grid network
EDGES = [
    "e00_01", "e01_00", "e01_02", "e02_01", "e02_03", "e03_02",
    "e10_11", "e11_10", "e11_12", "e12_11", "e12_13", "e13_12",
    "e20_21", "e21_20", "e21_22", "e22_21", "e22_23", "e23_22",
    "e30_31", "e31_30", "e31_32", "e32_31", "e32_33", "e33_32",
    "e00_10", "e10_00", "e10_20", "e20_10", "e20_30", "e30_20",
    "e01_11", "e11_01", "e11_21", "e21_11", "e21_31", "e31_21",
    "e02_12", "e12_02", "e12_22", "e22_12", "e22_32", "e32_22",
    "e03_13", "e13_03", "e13_23", "e23_13", "e23_33", "e33_23",
]

# Adjacency for building connected routes
ADJACENCY = {}
for e in EDGES:
    parts = e.replace("e", "").split("_")
    src, dst = parts[0], parts[1]
    if src not in ADJACENCY:
        ADJACENCY[src] = []
    ADJACENCY[src].append((dst, e))


def build_random_route(min_edges=4, max_edges=12):
    """Build a random connected route through the grid."""
    start_node = random.choice(list(ADJACENCY.keys()))
    current = start_node
    route_edges = []
    visited_edges = set()
    num_edges = random.randint(min_edges, max_edges)

    for _ in range(num_edges):
        if current not in ADJACENCY:
            break
        neighbors = ADJACENCY[current]
        # prefer unvisited edges
        unvisited = [(n, e) for n, e in neighbors if e not in visited_edges]
        if unvisited:
            next_node, edge = random.choice(unvisited)
        else:
            next_node, edge = random.choice(neighbors)

        route_edges.append(edge)
        visited_edges.add(edge)
        current = next_node

    return route_edges


def generate_routes(num_vehicles=210, output_file="sumo_files/vehicles.rou.xml"):
    """Generate vehicle route file."""
    root = ET.Element("routes")

    # Vehicle type
    vtype = ET.SubElement(root, "vType",
                          id="car", accel="2.6", decel="4.5",
                          sigma="0.5", length="5", minGap="2.5",
                          maxSpeed="16.67", color="0.0,1.0,0.0")

    vtype_fast = ET.SubElement(root, "vType",
                               id="fast_car", accel="3.5", decel="5.0",
                               sigma="0.3", length="5", minGap="2.0",
                               maxSpeed="22.22", color="0.0,0.5,1.0")

    generated = 0
    attempts = 0
    max_attempts = num_vehicles * 5

    while generated < num_vehicles and attempts < max_attempts:
        attempts += 1
        route_edges = build_random_route(min_edges=4, max_edges=15)

        if len(route_edges) < 3:
            continue

        # depart time: spread vehicles over first 600 seconds
        depart = round(random.uniform(0, 600), 1)
        vtype_id = random.choice(["car", "fast_car"])
        vid = f"v_{generated}"

        route = ET.SubElement(root, "vehicle",
                              id=vid, type=vtype_id,
                              depart=str(depart),
                              departSpeed="max",
                              departLane="best")

        route_elem = ET.SubElement(route, "route",
                                    edges=" ".join(route_edges))

        generated += 1

    # sort by depart time
    vehicles = [elem for elem in root if elem.tag == "vehicle"]
    vtypes = [elem for elem in root if elem.tag == "vType"]

    for v in vehicles:
        root.remove(v)

    vehicles.sort(key=lambda v: float(v.get("depart", "0")))
    for v in vehicles:
        root.append(v)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")

    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    tree.write(output_file, xml_declaration=True, encoding="UTF-8")

    print(f"Generated {generated} vehicle routes -> {output_file}")
    return generated


if __name__ == "__main__":
    generate_routes(210)
