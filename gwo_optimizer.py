"""
Grey Wolf Optimization (GWO) for Task Allocation in IoV
"""
import numpy as np
import config as cfg


def compute_task_latency(task, allocation):
    """Compute latency (ms) for a single task based on its allocation."""
    if allocation == cfg.LOC_VEHICLE:
        return 0.0 if not task.time_bounded else 9999.0

    elif allocation == cfg.LOC_RSU:
        if task.time_bounded:
            return (task.output_size / cfg.RATE_RSU_TO_VEHICLE) * 8
        return 9999.0

    elif allocation == cfg.LOC_NEIGHBOR_MBS:
        if task.time_bounded:
            trans = (task.output_size / cfg.RATE_RSU_TO_MBS) * 8
            ret = (task.output_size / cfg.RATE_RSU_TO_VEHICLE) * 8
            return trans + ret
        return 9999.0

    elif allocation == cfg.LOC_CLOUD:
        off = (task.data_size / cfg.RATE_VEHICLE_TO_CLOUD) * 8
        exe = (task.comp_req / (cfg.CLOUD_CONFIG["capacity_ghz"] * 1e9)) * 1000
        ret = (task.output_size / cfg.RATE_VEHICLE_TO_CLOUD) * 8
        return off + exe + ret

    return 9999.0


def compute_task_energy(task, allocation):
    """Compute energy consumption (mJ) for a single task."""
    if allocation == cfg.LOC_VEHICLE:
        return cfg.CACHE_POWER * task.output_size

    elif allocation == cfg.LOC_RSU:
        cache_e = cfg.CACHE_POWER * task.output_size
        ret_lat = (task.output_size / cfg.RATE_RSU_TO_VEHICLE) * 8
        return cache_e + cfg.RSU_POWER * ret_lat / 1000

    elif allocation == cfg.LOC_NEIGHBOR_MBS:
        cache_e = cfg.CACHE_POWER * task.output_size
        trans_lat = (task.output_size / cfg.RATE_RSU_TO_MBS) * 8
        ret_lat = (task.output_size / cfg.RATE_RSU_TO_VEHICLE) * 8
        return cache_e + cfg.MBS_POWER * trans_lat / 1000 + cfg.RSU_POWER * ret_lat / 1000

    elif allocation == cfg.LOC_CLOUD:
        off_lat = (task.data_size / cfg.RATE_VEHICLE_TO_CLOUD) * 8
        ret_lat = (task.output_size / cfg.RATE_VEHICLE_TO_CLOUD) * 8
        off_e = cfg.CLOUD_CONFIG["power_mw"] * off_lat / 1000
        exe_e = cfg.CLOUD_CONFIG["capacitance_coeff"] * task.comp_req * (cfg.CLOUD_CONFIG["capacity_ghz"] * 1e9)**2
        ret_e = cfg.CLOUD_CONFIG["power_mw"] * ret_lat / 1000
        return off_e + exe_e * 1000 + ret_e

    return 0


def fitness_function(alloc_vec, tasks, num_rsus=3, w1=None):
    """Weighted fitness: w1 * normalized_latency + (1-w1) * load_imbalance."""
    w1 = w1 if w1 is not None else cfg.FITNESS_W1
    total_latency = 0.0
    total_energy = 0.0
    rsu_loads = np.zeros(num_rsus)
    served = 0

    for i, task in enumerate(tasks):
        alloc = int(alloc_vec[i])
        lat = compute_task_latency(task, alloc)
        eng = compute_task_energy(task, alloc)

        if lat < 9000:
            total_latency += lat
            total_energy += eng
            served += 1
            rsu_idx = int(task.rsu_id.split("_")[1]) - 1 if task.rsu_id else 0
            if alloc == cfg.LOC_RSU:
                rsu_loads[rsu_idx] += 1
            elif alloc == cfg.LOC_NEIGHBOR_MBS:
                rsu_loads[rsu_idx] += 2
        else:
            total_latency += 500
            total_energy += 100

    if np.sum(rsu_loads) > 0:
        load_imbalance = np.sqrt(np.mean((rsu_loads - np.mean(rsu_loads))**2))
    else:
        load_imbalance = 0

    norm_latency = total_latency / (len(tasks) * 100 + 1)
    fitness = w1 * norm_latency + (1 - w1) * load_imbalance

    return {
        "fitness": fitness,
        "total_latency": total_latency,
        "total_energy": total_energy,
        "load_imbalance": load_imbalance,
        "rsu_loads": rsu_loads.tolist(),
        "served": served,
    }


def _valid_allocation(tasks):
    alloc = np.zeros(len(tasks), dtype=int)
    for i, t in enumerate(tasks):
        if t.time_bounded:
            alloc[i] = np.random.choice([cfg.LOC_RSU, cfg.LOC_NEIGHBOR_MBS, cfg.LOC_CLOUD])
        else:
            alloc[i] = np.random.choice([cfg.LOC_VEHICLE, cfg.LOC_CLOUD])
    return alloc


def run_gwo(tasks, population_size=None, max_iterations=None, w1=None):
    """Run GWO and return best allocation + convergence history."""
    pop = population_size or cfg.GWO_POPULATION
    max_iter = max_iterations or cfg.GWO_MAX_ITERATIONS
    n = len(tasks)
    nr = len(cfg.RSU_CONFIG)

    # Initialize
    wolves = np.array([_valid_allocation(tasks) for _ in range(pop)])
    fitness_vals = np.array([fitness_function(w, tasks, nr, w1)["fitness"] for w in wolves])

    idx = np.argsort(fitness_vals)
    alpha, beta, delta = wolves[idx[0]].copy(), wolves[idx[1]].copy(), wolves[idx[2]].copy()
    alpha_fit = fitness_vals[idx[0]]

    convergence = []

    for t in range(max_iter):
        a = 2.0 - 2.0 * t / max_iter

        for i in range(pop):
            new_w = np.zeros(n, dtype=int)
            for j in range(n):
                r1, r2 = np.random.random(2)
                A1, C1 = 2*a*r1-a, 2*r2
                X1 = alpha[j] - A1 * abs(C1 * alpha[j] - wolves[i][j])

                r1, r2 = np.random.random(2)
                A2, C2 = 2*a*r1-a, 2*r2
                X2 = beta[j] - A2 * abs(C2 * beta[j] - wolves[i][j])

                r1, r2 = np.random.random(2)
                A3, C3 = 2*a*r1-a, 2*r2
                X3 = delta[j] - A3 * abs(C3 * delta[j] - wolves[i][j])

                val = int(round((X1 + X2 + X3) / 3.0)) % 4
                valid = [cfg.LOC_RSU, cfg.LOC_NEIGHBOR_MBS, cfg.LOC_CLOUD] if tasks[j].time_bounded \
                    else [cfg.LOC_VEHICLE, cfg.LOC_CLOUD]
                new_w[j] = val if val in valid else np.random.choice(valid)

            wolves[i] = new_w

        fitness_vals = np.array([fitness_function(w, tasks, nr, w1)["fitness"] for w in wolves])
        idx = np.argsort(fitness_vals)

        if fitness_vals[idx[0]] < alpha_fit:
            alpha = wolves[idx[0]].copy()
            alpha_fit = fitness_vals[idx[0]]
        beta, delta = wolves[idx[1]].copy(), wolves[idx[2]].copy()

        alpha_detail = fitness_function(alpha, tasks, nr, w1)
        convergence.append({
            "iteration": t + 1,
            "fitness": alpha_fit,
            "latency": alpha_detail["total_latency"],
            "energy": alpha_detail["total_energy"],
            "load_imbalance": alpha_detail["load_imbalance"],
            "a_parameter": round(a, 4),
        })

    final = fitness_function(alpha, tasks, nr, w1)
    alloc_summary = {loc: 0 for loc in cfg.LOCATION_NAMES.values()}
    for v in alpha:
        alloc_summary[cfg.LOCATION_NAMES[int(v)]] += 1

    return {
        "best_allocation": alpha.tolist(),
        "best_fitness": alpha_fit,
        "final_metrics": final,
        "convergence": convergence,
        "allocation_summary": alloc_summary,
    }
