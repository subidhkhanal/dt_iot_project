"""
Physical Layer — Supports SUMO+TraCI and Standalone Simulation
"""
import numpy as np
import config as cfg

# Try importing TraCI
try:
    import traci
    TRACI_AVAILABLE = True
except ImportError:
    TRACI_AVAILABLE = False


# ═══════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════
class Vehicle:
    def __init__(self, vid, x, y, speed, heading=0.0):
        self.id = vid
        self.x = x
        self.y = y
        self.speed = speed
        self.heading = heading
        self.tasks = []
        self.connected_rsu = None

    def move(self, dt=1.0):
        speed_ms = self.speed * 1000 / 3600
        self.heading += np.random.uniform(-0.15, 0.15)
        self.x += speed_ms * np.cos(self.heading) * dt
        self.y += speed_ms * np.sin(self.heading) * dt
        bnd = cfg.ROAD_BOUNDS
        if self.x < bnd["x_min"] or self.x > bnd["x_max"]:
            self.heading = np.pi - self.heading
            self.x = np.clip(self.x, bnd["x_min"], bnd["x_max"])
        if self.y < bnd["y_min"] or self.y > bnd["y_max"]:
            self.heading = -self.heading
            self.y = np.clip(self.y, bnd["y_min"], bnd["y_max"])

    def to_dict(self):
        return {
            "id": self.id, "x": round(self.x, 1), "y": round(self.y, 1),
            "speed": round(self.speed, 1), "connected_rsu": self.connected_rsu,
            "num_tasks": len(self.tasks),
        }


class Task:
    def __init__(self, task_id, vehicle_id, rsu_id):
        self.id = task_id
        self.vehicle_id = vehicle_id
        self.rsu_id = rsu_id
        self.data_size = np.random.uniform(*cfg.TASK_DATA_SIZE_RANGE)
        self.output_size = np.random.uniform(*cfg.TASK_OUTPUT_SIZE_RANGE)
        self.comp_req = np.random.uniform(*cfg.TASK_COMP_RANGE)
        self.time_bounded = np.random.random() < cfg.TIME_BOUNDED_PROB
        self.allocated_to = None
        self.latency = 0.0
        self.energy = 0.0

    def to_dict(self):
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "rsu_id": self.rsu_id,
            "data_size_kb": round(self.data_size, 1),
            "output_size_kb": round(self.output_size, 1),
            "comp_cycles": f"{self.comp_req:.2e}",
            "time_bounded": self.time_bounded,
            "allocated_to": cfg.LOCATION_NAMES.get(self.allocated_to, "Unassigned"),
            "latency_ms": round(self.latency, 2),
            "energy_mj": round(self.energy, 2),
        }


class RSU:
    def __init__(self, rsu_cfg):
        self.id = rsu_cfg["id"]
        self.x = rsu_cfg["x"]
        self.y = rsu_cfg["y"]
        self.coverage = rsu_cfg["coverage"]
        self.capacity = rsu_cfg["capacity_mhz"]
        self.cache_mb = rsu_cfg["cache_mb"]
        self.current_load = 0
        self.vehicles_served = []
        self.cached_tasks = set()

    def in_coverage(self, vx, vy):
        return np.sqrt((self.x - vx)**2 + (self.y - vy)**2) <= self.coverage

    def to_dict(self):
        return {
            "id": self.id, "x": self.x, "y": self.y,
            "coverage": self.coverage, "load": self.current_load,
            "vehicles_served": len(self.vehicles_served),
            "cached_tasks": len(self.cached_tasks),
            "utilization_pct": round(min(self.current_load / 20 * 100, 100), 1),
        }


def find_nearest_rsu(x, y, rsus):
    dists = [np.sqrt((r.x - x)**2 + (r.y - y)**2) for r in rsus]
    return rsus[np.argmin(dists)]


# ═══════════════════════════════════════════════
# SUMO Physical Layer (with TraCI)
# ═══════════════════════════════════════════════
class SUMOPhysicalLayer:
    """Physical layer using Eclipse SUMO + TraCI."""

    def __init__(self, use_gui=False):
        if not TRACI_AVAILABLE:
            raise RuntimeError("TraCI not available. Install SUMO: sudo apt install sumo sumo-tools")

        self.use_gui = use_gui
        self.time_step = 0
        self.vehicles = []
        self.rsus = []
        self.tasks = []
        self.task_counter = 0
        self._vehicle_task_map = {}  # vid -> list of Task objects

        # Initialize RSUs
        for r in cfg.RSU_CONFIG:
            self.rsus.append(RSU(r))

        # Start SUMO
        sumo_cmd = "sumo-gui" if use_gui else "sumo"
        traci.start([sumo_cmd, "-c", cfg.SUMO_CFG, "--start", "--quit-on-end"])
        print(f"[SUMO] Started {'with GUI' if use_gui else 'headless'}")

    def step(self):
        """Advance SUMO by one step and collect vehicle data."""
        self.time_step += 1

        # Step SUMO simulation
        traci.simulationStep()

        # Reset RSU state
        for r in self.rsus:
            r.current_load = 0
            r.vehicles_served = []

        # Collect vehicle data from SUMO
        self.vehicles = []
        self.tasks = []
        sumo_vehicle_ids = traci.vehicle.getIDList()

        for vid in sumo_vehicle_ids:
            x, y = traci.vehicle.getPosition(vid)
            speed_ms = traci.vehicle.getSpeed(vid)
            speed_kmh = speed_ms * 3.6
            angle = traci.vehicle.getAngle(vid)

            v = Vehicle(vid, x, y, speed_kmh, np.radians(angle))
            nearest_rsu = find_nearest_rsu(x, y, self.rsus)
            v.connected_rsu = nearest_rsu.id
            nearest_rsu.vehicles_served.append(vid)

            # Generate tasks (reuse if vehicle seen before, else create new)
            if vid not in self._vehicle_task_map:
                n_tasks = np.random.randint(*cfg.TASKS_PER_VEHICLE)
                tasks_for_v = []
                for k in range(n_tasks):
                    self.task_counter += 1
                    t = Task(f"T_{self.task_counter:04d}", vid, nearest_rsu.id)
                    tasks_for_v.append(t)
                self._vehicle_task_map[vid] = tasks_for_v
            else:
                # Update RSU assignment for existing tasks
                for t in self._vehicle_task_map[vid]:
                    t.rsu_id = nearest_rsu.id
                    t.allocated_to = None  # reset for new optimization

            v.tasks = self._vehicle_task_map[vid]
            self.tasks.extend(v.tasks)
            self.vehicles.append(v)

        # Clean up departed vehicles
        active_ids = set(sumo_vehicle_ids)
        departed = [vid for vid in self._vehicle_task_map if vid not in active_ids]
        for vid in departed:
            del self._vehicle_task_map[vid]

        return self.get_state()

    def get_state(self):
        return {
            "time_step": self.time_step,
            "vehicles": [v.to_dict() for v in self.vehicles],
            "rsus": [r.to_dict() for r in self.rsus],
            "tasks": [t.to_dict() for t in self.tasks],
            "num_vehicles": len(self.vehicles),
            "num_tasks": len(self.tasks),
            "source": "SUMO",
        }

    def is_running(self):
        try:
            return traci.simulation.getMinExpectedNumber() > 0
        except Exception:
            return False

    def close(self):
        try:
            traci.close()
            print("[SUMO] Closed")
        except Exception:
            pass


# ═══════════════════════════════════════════════
# Standalone Physical Layer (no SUMO needed)
# ═══════════════════════════════════════════════
class StandalonePhysicalLayer:
    """Built-in simulation without SUMO dependency."""

    def __init__(self, num_vehicles=None):
        self.num_vehicles = num_vehicles or cfg.NUM_VEHICLES_STANDALONE
        self.time_step = 0
        self.vehicles = []
        self.rsus = []
        self.tasks = []

        for r in cfg.RSU_CONFIG:
            self.rsus.append(RSU(r))
        self._init_vehicles()

    def _init_vehicles(self):
        task_counter = 0
        bnd = cfg.ROAD_BOUNDS
        for i in range(self.num_vehicles):
            x = np.random.uniform(bnd["x_min"], bnd["x_max"])
            y = np.random.uniform(bnd["y_min"], bnd["y_max"])
            speed = np.random.uniform(*cfg.VEHICLE_SPEED_RANGE)
            heading = np.random.uniform(0, 2 * np.pi)
            v = Vehicle(f"v_{i}", x, y, speed, heading)

            nearest = find_nearest_rsu(x, y, self.rsus)
            v.connected_rsu = nearest.id

            n_tasks = np.random.randint(*cfg.TASKS_PER_VEHICLE)
            for k in range(n_tasks):
                task_counter += 1
                t = Task(f"T_{task_counter:04d}", v.id, nearest.id)
                v.tasks.append(t)
                self.tasks.append(t)

            self.vehicles.append(v)

    def step(self):
        self.time_step += 1
        for r in self.rsus:
            r.current_load = 0
            r.vehicles_served = []

        for v in self.vehicles:
            v.move(dt=1.0)
            nearest = find_nearest_rsu(v.x, v.y, self.rsus)
            v.connected_rsu = nearest.id
            nearest.vehicles_served.append(v.id)
            for t in v.tasks:
                t.rsu_id = nearest.id
                t.allocated_to = None

        self.tasks = []
        for v in self.vehicles:
            self.tasks.extend(v.tasks)

        if self.time_step % 5 == 0:
            self._refresh_tasks()

        return self.get_state()

    def _refresh_tasks(self):
        n = max(1, len(self.tasks) // 5)
        indices = np.random.choice(len(self.tasks), min(n, len(self.tasks)), replace=False)
        for idx in indices:
            old = self.tasks[idx]
            new_t = Task(old.id, old.vehicle_id, old.rsu_id)
            self.tasks[idx] = new_t
            for v in self.vehicles:
                if v.id == old.vehicle_id:
                    for ti, t in enumerate(v.tasks):
                        if t.id == old.id:
                            v.tasks[ti] = new_t
                            break
                    break

    def get_state(self):
        return {
            "time_step": self.time_step,
            "vehicles": [v.to_dict() for v in self.vehicles],
            "rsus": [r.to_dict() for r in self.rsus],
            "tasks": [t.to_dict() for t in self.tasks],
            "num_vehicles": len(self.vehicles),
            "num_tasks": len(self.tasks),
            "source": "Standalone",
        }

    def is_running(self):
        return True

    def close(self):
        pass
