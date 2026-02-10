"""
Console runner — Test the full pipeline without the dashboard.
Usage:
    python run.py --sumo-gui     # SUMO with GUI
    python run.py --sumo         # SUMO headless
    python run.py --sim          # Standalone simulation (no SUMO)
"""
import sys
import time
import json
from physical_layer import SUMOPhysicalLayer, StandalonePhysicalLayer
from digital_twin import DigitalTwinLayer
from gwo_optimizer import run_gwo
import config as cfg


def main():
    mode = "--sim"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    # ── Initialize Physical Layer ──
    print("=" * 60)
    print(" Digital Twin IoV — Console Runner")
    print("=" * 60)

    if mode == "--sumo-gui":
        print("[MODE] SUMO with GUI")
        physical = SUMOPhysicalLayer(use_gui=True)
    elif mode == "--sumo":
        print("[MODE] SUMO headless")
        physical = SUMOPhysicalLayer(use_gui=False)
    else:
        print("[MODE] Standalone simulation (no SUMO)")
        physical = StandalonePhysicalLayer(num_vehicles=50)

    # ── Initialize Digital Twin ──
    dt = DigitalTwinLayer()
    print(f"[DT] Initialized with {len(cfg.RSU_CONFIG)} RSU twins")

    # ── Run simulation loop ──
    num_steps = 10
    print(f"\n[SIM] Running {num_steps} time steps...\n")

    results = []
    for step in range(num_steps):
        # 1. Physical layer step
        state = physical.step()

        # 2. DT sync
        sync = dt.sync_from_physical(state, time.time())

        # 3. GWO optimization
        gwo = run_gwo(physical.tasks, population_size=20, max_iterations=50)

        # 4. Apply allocations
        for i, task in enumerate(physical.tasks):
            if i < len(gwo["best_allocation"]):
                task.allocated_to = gwo["best_allocation"][i]

        # 5. Record
        r = {
            "step": state["time_step"],
            "vehicles": state["num_vehicles"],
            "tasks": state["num_tasks"],
            "fitness": round(gwo["best_fitness"], 4),
            "latency_ms": round(gwo["final_metrics"]["total_latency"], 1),
            "energy_mj": round(gwo["final_metrics"]["total_energy"], 1),
            "load_imbalance": round(gwo["final_metrics"]["load_imbalance"], 4),
            "served": gwo["final_metrics"]["served"],
            "avg_aoi": sync["avg_aoi"],
            "allocation": gwo["allocation_summary"],
        }
        results.append(r)

        print(f"  Step {r['step']:3d} | Vehicles: {r['vehicles']:3d} | Tasks: {r['tasks']:3d} | "
              f"Fitness: {r['fitness']:.4f} | Latency: {r['latency_ms']:.0f}ms | "
              f"Load Imb: {r['load_imbalance']:.4f} | AoI: {r['avg_aoi']:.3f}s")

    # ── Summary ──
    print("\n" + "=" * 60)
    print(" Summary")
    print("=" * 60)
    avg_fitness = sum(r["fitness"] for r in results) / len(results)
    avg_latency = sum(r["latency_ms"] for r in results) / len(results)
    avg_energy = sum(r["energy_mj"] for r in results) / len(results)
    print(f"  Avg Fitness:     {avg_fitness:.4f}")
    print(f"  Avg Latency:     {avg_latency:.1f} ms")
    print(f"  Avg Energy:      {avg_energy:.1f} mJ")
    print(f"  DT Total Syncs:  {dt.total_syncs}")
    print(f"  Last Allocation: {results[-1]['allocation']}")

    # Cleanup
    physical.close()

    # Save results
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[SAVED] results.json")


if __name__ == "__main__":
    main()
