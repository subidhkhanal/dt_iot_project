"""
Digital Twin Layer — Backed by Eclipse Ditto
════════════════════════════════════════════════

Two modes:
  1. DITTO MODE  — Twins stored in Eclipse Ditto (real DT platform)
  2. MEMORY MODE — Twins stored in Python (fallback if Ditto unavailable)

Auto-detects Ditto. If running → uses Ditto. If not → falls back to memory.
Both modes expose the SAME interface.

Architecture:
    Physical System ──(State Sync)──► Digital Twin Layer (Ditto / Memory)
                                           │
                                      Exposed States
                                           │
                                           ▼
                                     GWO Optimization
"""
import time
import copy
import numpy as np
import config as cfg

try:
    from ditto_client import DittoClient
    DITTO_CLIENT_AVAILABLE = True
except ImportError:
    DITTO_CLIENT_AVAILABLE = False


class DigitalTwinNode:
    """In-memory virtual replica of a single physical component."""

    def __init__(self, node_type, node_id, properties):
        self.node_type = node_type
        self.node_id = node_id
        self.properties = properties
        self.last_sync_time = 0.0
        self.sync_count = 0
        self.aoi = 0.0

    def update(self, new_properties, current_time):
        self.aoi = current_time - self.last_sync_time if self.last_sync_time > 0 else 0.0
        self.properties = copy.deepcopy(new_properties)
        self.last_sync_time = current_time
        self.sync_count += 1

    def to_dict(self):
        return {
            "node_type": self.node_type,
            "node_id": self.node_id,
            "properties": self.properties,
            "last_sync": round(self.last_sync_time, 3),
            "aoi": round(self.aoi, 3),
            "sync_count": self.sync_count,
        }


class DigitalTwinLayer:
    """
    Manages Digital Twins for all IoV components.
    Uses Eclipse Ditto when available, falls back to in-memory.
    """

    def __init__(self, force_memory=False):
        self.vehicle_twins = {}
        self.rsu_twins = {}
        self.mbs_twin = None
        self.cloud_twin = None
        self.sync_log = []
        self.total_syncs = 0
        self.creation_time = time.time()

        self.ditto = None
        self.ditto_connected = False
        self.backend = "memory"

        if not force_memory and DITTO_CLIENT_AVAILABLE:
            try:
                self.ditto = DittoClient()
                if self.ditto.is_connected():
                    self.ditto_connected = True
                    self.backend = "Eclipse Ditto"
                    print("[DT] Backend: Eclipse Ditto")
                else:
                    print("[DT] Ditto not reachable, using in-memory")
            except Exception as e:
                print(f"[DT] Ditto error: {e}, using in-memory")
        else:
            print("[DT] Backend: In-Memory")

        self._init_infrastructure_twins()

    def _init_infrastructure_twins(self):
        for r in cfg.RSU_CONFIG:
            self.rsu_twins[r["id"]] = DigitalTwinNode(
                "rsu", r["id"],
                {"x": r["x"], "y": r["y"], "coverage": r["coverage"],
                 "capacity": r["capacity_mhz"], "cache_mb": r["cache_mb"],
                 "load": 0, "vehicles_served": 0, "cached_tasks": 0,
                 "utilization_pct": 0}
            )
        self.mbs_twin = DigitalTwinNode(
            "mbs", cfg.MBS_CONFIG["id"],
            {"x": cfg.MBS_CONFIG["x"], "y": cfg.MBS_CONFIG["y"],
             "capacity": cfg.MBS_CONFIG["capacity_mhz"],
             "cache_mb": cfg.MBS_CONFIG["cache_mb"]}
        )
        self.cloud_twin = DigitalTwinNode(
            "cloud", "CLOUD",
            {"capacity_ghz": cfg.CLOUD_CONFIG["capacity_ghz"],
             "power_mw": cfg.CLOUD_CONFIG["power_mw"]}
        )

    # ═══════════════════════════════════════════
    # Core State Sync
    # ═══════════════════════════════════════════
    def sync_from_physical(self, physical_state, current_time):
        """
        STATE SYNC: Push physical state into the Digital Twin layer.
        Updates both in-memory twins AND Ditto (if connected).
        """
        rel_time = current_time - self.creation_time

        sync_record = {
            "time": round(rel_time, 3),
            "time_step": physical_state["time_step"],
            "vehicles_synced": 0,
            "rsus_synced": 0,
            "ditto_synced": 0,
            "source": physical_state.get("source", "unknown"),
            "backend": self.backend,
        }

        # ── Sync Vehicles ──
        for v_data in physical_state["vehicles"]:
            vid = v_data["id"]

            # In-memory
            if vid not in self.vehicle_twins:
                self.vehicle_twins[vid] = DigitalTwinNode("vehicle", vid, {})
                self.vehicle_twins[vid].last_sync_time = rel_time
            self.vehicle_twins[vid].update(v_data, rel_time)
            sync_record["vehicles_synced"] += 1

            # Ditto
            if self.ditto_connected:
                try:
                    if self.vehicle_twins[vid].sync_count <= 1:
                        self.ditto.create_thing(
                            thing_id=vid,
                            attributes={"type": "vehicle", "id": vid},
                            features={})
                    success = self.ditto.update_vehicle_twin(
                        vehicle_id=vid,
                        x=v_data.get("x", 0), y=v_data.get("y", 0),
                        speed=v_data.get("speed", 0),
                        connected_rsu=v_data.get("connected_rsu", ""),
                        num_tasks=v_data.get("num_tasks", 0),
                        sync_time=rel_time)
                    if success:
                        sync_record["ditto_synced"] += 1
                except Exception:
                    pass

        # ── Sync RSUs ──
        for r_data in physical_state["rsus"]:
            rid = r_data["id"]
            if rid in self.rsu_twins:
                if self.rsu_twins[rid].last_sync_time == 0:
                    self.rsu_twins[rid].last_sync_time = rel_time
                self.rsu_twins[rid].update(r_data, rel_time)
                sync_record["rsus_synced"] += 1

                if self.ditto_connected:
                    try:
                        success = self.ditto.update_rsu_twin(
                            rsu_id=rid,
                            load=r_data.get("load", 0),
                            vehicles_served=r_data.get("vehicles_served", 0),
                            utilization_pct=r_data.get("utilization_pct", 0),
                            cached_tasks=r_data.get("cached_tasks", 0),
                            sync_time=rel_time)
                        if success:
                            sync_record["ditto_synced"] += 1
                    except Exception:
                        pass

        # ── Remove stale vehicles ──
        active_ids = {v["id"] for v in physical_state["vehicles"]}
        stale = [vid for vid in self.vehicle_twins if vid not in active_ids]
        for vid in stale:
            del self.vehicle_twins[vid]
            if self.ditto_connected:
                try:
                    self.ditto.delete_thing(vid)
                except Exception:
                    pass

        # ── AoI ──
        all_aois = [t.aoi for t in self.vehicle_twins.values()]
        all_aois += [t.aoi for t in self.rsu_twins.values()]
        sync_record["avg_aoi"] = round(np.mean(all_aois), 4) if all_aois else 0
        sync_record["max_aoi"] = round(max(all_aois), 4) if all_aois else 0

        self.total_syncs += 1
        self.sync_log.append(sync_record)
        return sync_record

    # ═══════════════════════════════════════════
    # Expose State to GWO
    # ═══════════════════════════════════════════
    def get_exposed_state(self):
        return {
            "vehicles": {vid: t.to_dict() for vid, t in self.vehicle_twins.items()},
            "rsus": {rid: t.to_dict() for rid, t in self.rsu_twins.items()},
            "mbs": self.mbs_twin.to_dict() if self.mbs_twin else None,
            "cloud": self.cloud_twin.to_dict() if self.cloud_twin else None,
            "total_syncs": self.total_syncs,
            "dt_uptime": round(time.time() - self.creation_time, 1),
            "backend": self.backend,
            "ditto_connected": self.ditto_connected,
        }

    def get_rsu_loads(self):
        return {rid: {
            "load": t.properties.get("load", 0),
            "vehicles_served": t.properties.get("vehicles_served", 0),
            "utilization_pct": t.properties.get("utilization_pct", 0),
        } for rid, t in self.rsu_twins.items()}

    def get_vehicle_positions(self):
        return [{"id": vid, "x": t.properties.get("x", 0), "y": t.properties.get("y", 0),
                 "speed": t.properties.get("speed", 0),
                 "connected_rsu": t.properties.get("connected_rsu", "N/A")}
                for vid, t in self.vehicle_twins.items()]

    def get_sync_stats(self):
        if not self.sync_log:
            return {"total_syncs": 0, "avg_aoi": 0, "max_aoi": 0,
                    "vehicles_synced": 0, "rsus_synced": 0, "ditto_synced": 0,
                    "backend": self.backend}
        latest = self.sync_log[-1]
        return {
            "total_syncs": self.total_syncs,
            "avg_aoi": latest.get("avg_aoi", 0),
            "max_aoi": latest.get("max_aoi", 0),
            "vehicles_synced": latest.get("vehicles_synced", 0),
            "rsus_synced": latest.get("rsus_synced", 0),
            "ditto_synced": latest.get("ditto_synced", 0),
            "backend": self.backend,
        }

    def get_aoi_history(self):
        return [{"step": s["time_step"], "avg_aoi": s["avg_aoi"]} for s in self.sync_log]

    # ═══════════════════════════════════════════
    # Ditto Verification
    # ═══════════════════════════════════════════
    def get_ditto_status(self):
        if not self.ditto_connected:
            return {"connected": False, "backend": "In-Memory",
                    "things_count": len(self.vehicle_twins) + len(self.rsu_twins) + 2,
                    "url": "N/A"}
        try:
            things = self.ditto.list_things()
            return {"connected": True, "backend": "Eclipse Ditto",
                    "things_count": len(things),
                    "url": "http://localhost:8080/api/2/things",
                    "things": [t.get("thingId", "") for t in things]}
        except Exception:
            return {"connected": True, "backend": "Eclipse Ditto (error)",
                    "things_count": 0, "url": "http://localhost:8080/api/2/things"}

    def verify_ditto_sync(self, thing_id):
        if not self.ditto_connected:
            return None
        try:
            return self.ditto.get_thing(thing_id)
        except Exception:
            return None
