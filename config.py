"""
Configuration — Digital Twin IoV Task Allocation
"""

# ═══ SUMO Settings ═══
SUMO_CFG = "sumo_files/simulation.sumocfg"
SUMO_NET = "sumo_files/network.net.xml"
SUMO_STEP_LENGTH = 1.0     # seconds per step

# ═══ Network Bounds ═══
ROAD_BOUNDS = {"x_min": 0, "x_max": 1500, "y_min": 0, "y_max": 1500}

# ═══ RSU Configuration ═══
#   3 RSUs placed at strategic intersections in the 4x4 grid
RSU_CONFIG = [
    {"id": "RSU_1", "x": 250,  "y": 250,   "coverage": 450, "capacity_mhz": 3000, "cache_mb": 512},
    {"id": "RSU_2", "x": 1250, "y": 250,    "coverage": 450, "capacity_mhz": 3000, "cache_mb": 512},
    {"id": "RSU_3", "x": 750,  "y": 1250,   "coverage": 450, "capacity_mhz": 3000, "cache_mb": 512},
]

# ═══ MBS Configuration ═══
MBS_CONFIG = {
    "id": "MBS_1", "x": 750, "y": 750,
    "coverage": 1200, "capacity_mhz": 10000, "cache_mb": 2048
}

# ═══ Cloud Configuration ═══
CLOUD_CONFIG = {
    "capacity_ghz": 15.0,
    "power_mw": 400,
    "capacitance_coeff": 1e-28,
}

# ═══ Task Configuration ═══
TASKS_PER_VEHICLE = (1, 4)
TASK_DATA_SIZE_RANGE = (200, 3000)       # KB
TASK_OUTPUT_SIZE_RANGE = (20, 1000)      # KB
TASK_COMP_RANGE = (1e9, 5e9)             # cycles
TIME_BOUNDED_PROB = 0.6

# ═══ Communication Rates (Mbps) ═══
RATE_RSU_TO_VEHICLE = 50.0
RATE_RSU_TO_RSU = 100.0
RATE_RSU_TO_MBS = 200.0
RATE_MBS_TO_CLOUD = 500.0
RATE_VEHICLE_TO_CLOUD = 20.0

# ═══ Power Parameters ═══
CACHE_POWER = 0.01         # W/KB
RSU_POWER = 200            # mW
MBS_POWER = 300            # mW

# ═══ GWO Parameters ═══
GWO_POPULATION = 30
GWO_MAX_ITERATIONS = 100
FITNESS_W1 = 0.5

# ═══ DT Parameters ═══
DT_SYNC_INTERVAL = 1.0
AOI_THRESHOLD = 3.0

# ═══ Execution Locations ═══
LOC_VEHICLE = 0
LOC_RSU = 1
LOC_NEIGHBOR_MBS = 2
LOC_CLOUD = 3

LOCATION_NAMES = {
    0: "Vehicle Cache",
    1: "Primary RSU",
    2: "Neighbor RSU/MBS",
    3: "Cloud",
}

# ═══ Standalone Simulation ═══
NUM_VEHICLES_STANDALONE = 50
VEHICLE_SPEED_RANGE = (30, 80)  # km/h
