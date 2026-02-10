# Digital Twin Enabled IoV Task Allocation Using Grey Wolf Optimization

## Project Structure

```
dt_iot_project/
├── sumo_files/                  # SUMO scenario files
│   ├── network.nod.xml          # Node definitions (4x4 grid intersections)
│   ├── network.edg.xml          # Edge definitions (bidirectional roads)
│   ├── simulation.sumocfg       # SUMO configuration
│   └── vehicles.rou.xml         # Generated vehicle routes (210 vehicles)
│
├── config.py                    # All parameters (RSU, MBS, Cloud, GWO, DT)
├── physical_layer.py            # Physical layer (SUMO + Standalone modes)
├── digital_twin.py              # Digital Twin layer with State Sync & AoI
├── gwo_optimizer.py             # Grey Wolf Optimization for task allocation
├── generate_routes.py           # SUMO route generator
├── run.py                       # Console runner (for testing)
├── dashboard.py                 # Streamlit dashboard (main showpiece)
├── setup.sh                     # One-command setup script
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Quick Start (3 Steps)

### Step 1: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install SUMO (Ubuntu/Debian)
sudo add-apt-repository ppa:sumo/stable
sudo apt update
sudo apt install sumo sumo-tools sumo-gui
```

### Step 2: Build SUMO Network

```bash
# One command setup
chmod +x setup.sh
./setup.sh
```

Or manually:
```bash
cd sumo_files
netconvert --node-files=network.nod.xml --edge-files=network.edg.xml --output-file=network.net.xml --no-turnarounds=true
cd ..
python3 generate_routes.py
```

### Step 3: Run

**Dashboard (recommended for demo/panel presentation):**
```bash
streamlit run dashboard.py
```
Opens at http://localhost:8501

**Console test:**
```bash
python3 run.py --sim          # Without SUMO
python3 run.py --sumo         # With SUMO headless
python3 run.py --sumo-gui     # With SUMO GUI
```

## How It Works

```
┌─────────────────────────┐      State Sync      ┌───────────────────────────┐
│    PHYSICAL LAYER       │ ────────────────────► │    DIGITAL TWIN LAYER     │
│                         │                       │                           │
│  SUMO Simulation        │                       │  Vehicle Twins (position, │
│  • 210 vehicles         │                       │    speed, RSU connection)  │
│  • 4x4 grid network     │                       │  RSU Twins (load, cache,  │
│  • Traffic lights        │                       │    coverage, utilization)  │
│  • 3 RSUs + 1 MBS       │                       │  MBS Twin                 │
│  • Cloud server          │                       │  Cloud Twin               │
│                         │                       │  AoI Tracking             │
└────────┬────────────────┘                       └────────────┬──────────────┘
         │                                                     │
         │                                              Exposed States
         │                                                     │
         │              ┌─────────────────────────┐            │
         │              │   OPTIMIZATION LAYER     │◄───────────┘
         │              │                          │
         │              │  Grey Wolf Optimization  │
         │              │  • Population: 30 wolves │
         │              │  • Iterations: 100       │
         │              │  • Fitness: latency +    │
         │              │    load imbalance        │
         │              │  • 4 execution options:  │
         │              │    Vehicle/RSU/MBS/Cloud  │
         │              └────────────┬─────────────┘
         │                           │
         │     Decision Dispatch     │
         │◄──────────────────────────┘
         │
         ▼
    EXECUTION
    (Tasks processed at assigned locations)
```

## Dashboard Tabs

| Tab | What It Shows |
|-----|---------------|
| **Physical & DT** | Side-by-side maps — physical layer (blue) and DT mirror (green) with vehicles, RSUs, MBS, coverage zones. State Sync status bar with AoI. |
| **GWO Optimization** | Convergence plots: fitness, latency, load imbalance, parameter 'a' (exploration→exploitation). Final optimization results. |
| **Task Allocation** | Donut chart of task distribution across Vehicle/RSU/MBS/Cloud. Per-RSU stacked bar chart. Full task detail table. |
| **RSU Status** | Per-RSU gauge meters showing utilization %. Load counts, vehicles served. Load comparison bar chart with mean line. |
| **History** | Multi-step trends: fitness, latency, energy, load imbalance, AoI over time. Vehicle/task count dynamics. |

## SUMO Network Details

- **Topology**: 4×4 grid (16 intersections)
- **Roads**: Bidirectional, 2 lanes each, 500m between intersections
- **Speed limit**: 60 km/h (16.67 m/s)
- **Traffic control**: Traffic lights at all intersections
- **Vehicles**: 210 vehicles, 2 types (car + fast_car)
- **Simulation duration**: 3600 seconds

## RSU Placement

| RSU | Position | Coverage |
|-----|----------|----------|
| RSU_1 | (250, 250) | 450m radius |
| RSU_2 | (1250, 250) | 450m radius |
| RSU_3 | (750, 1250) | 450m radius |
| MBS | (750, 750) | 1200m radius |

## Key Files Explained

### physical_layer.py
Two classes:
- `SUMOPhysicalLayer` — Uses TraCI to get real vehicle data from SUMO
- `StandalonePhysicalLayer` — Built-in simulation for testing without SUMO

Both expose the same interface: `.step()`, `.get_state()`, `.is_running()`

### digital_twin.py
- `DigitalTwinNode` — Virtual replica of one component (vehicle/RSU/MBS/cloud)
- `DigitalTwinLayer` — Manages all twins, performs State Sync, tracks AoI
- Key method: `sync_from_physical()` — called every time step

### gwo_optimizer.py
- Implements GWO with alpha/beta/delta wolf hierarchy
- Fitness function: `w1 × normalized_latency + (1-w1) × load_imbalance`
- Respects time-flag constraints (time-bounded vs time-unbounded tasks)
- Returns: best allocation, convergence history, metrics

## What to Tell the Panel

1. "The Physical Layer runs in Eclipse SUMO — an industry-standard traffic simulator"
2. "The Digital Twin Layer maintains real-time virtual replicas of every vehicle, RSU, and network component"
3. "State Synchronization happens every time step via TraCI, with Age of Information tracking"
4. "The GWO Optimization Layer reads the DT's exposed state to make task allocation decisions"
5. "Decisions are dispatched back to the Physical Layer for execution"
6. "The dashboard shows both layers running simultaneously — physical in blue, DT mirror in green"
