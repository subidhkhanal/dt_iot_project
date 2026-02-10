# Digital Twin IoV — Complete Auto Setup

## READ THIS ENTIRE FILE AND EXECUTE ALL STEPS AUTOMATICALLY. DO NOT ASK QUESTIONS.

## System: Windows 10, VS Code, Python 3.x, Docker Desktop

---

## PHASE 1: PYTHON DEPENDENCIES

Run in terminal:
```bash
pip install streamlit plotly pandas numpy requests
```

---

## PHASE 2: SUMO SETUP

### Check if SUMO is installed:
```bash
where netconvert
```

### If netconvert IS found:
```bash
cd sumo_files
netconvert --node-files=network.nod.xml --edge-files=network.edg.xml --output-file=network.net.xml --no-turnarounds=true
cd ..
python generate_routes.py
```

### If netconvert is NOT found:
Tell the user: "SUMO is not installed. The dashboard will run in standalone mode without SUMO. To add SUMO later, download it from https://sumo.dlr.de/docs/Downloads.php and add the bin folder to PATH."

Skip the netconvert and route generation commands. The dashboard works without SUMO.

---

## PHASE 3: ECLIPSE DITTO (DIGITAL TWIN PLATFORM)

### Check if Docker is available:
```bash
docker --version
```

### If Docker IS available:

Start Eclipse Ditto:
```bash
docker-compose up -d
```

Wait for Ditto to be ready (takes about 30-60 seconds). Check with:
```bash
timeout 5 curl -s http://localhost:8080/health
```

If curl is not available on Windows, use Python instead:
```bash
python -c "import requests; r=requests.get('http://localhost:8080/health', timeout=10); print(r.text)"
```

If health check fails, wait 15 more seconds and retry. Ditto takes time to start all services. Retry up to 4 times.

Once Ditto is healthy, initialize the Digital Twin Things:
```bash
python init_ditto.py
```

Expected output: Should show policy created, 3 RSU Things created, MBS Thing created, Cloud Thing created, and total Things count.

### If Docker is NOT available:
Tell the user: "Docker Desktop is not installed. The dashboard will use in-memory Digital Twins instead of Eclipse Ditto. To add Ditto later, install Docker Desktop from https://www.docker.com/products/docker-desktop/ then re-run this setup."

Skip docker-compose and init_ditto.py. The dashboard works without Ditto.

---

## PHASE 4: TEST THE PIPELINE

Run:
```bash
python run.py --sim
```

Expected: 10 time steps with vehicles, tasks, fitness, latency, load imbalance, AoI values. If Ditto is running, it should show "Backend: Eclipse Ditto". Otherwise "Backend: In-Memory".

If this succeeds, everything is working.

---

## PHASE 5: LAUNCH DASHBOARD

Run:
```bash
streamlit run dashboard.py
```

This opens at http://localhost:8501

Tell the user:
1. The dashboard is now running at http://localhost:8501
2. Click "Init" in the sidebar to start the simulation
3. Click "Run 5 Steps" to see the full pipeline in action
4. Check the "Eclipse Ditto" tab to see the DT platform integration
5. The 6 tabs show: Physical Layer, DT Mirror, GWO Optimization, Task Allocation, RSU Status, Performance History, and Eclipse Ditto status

If Ditto is connected, the "Eclipse Ditto" tab shows all Things stored in the platform with live verification.
If Ditto is not connected, the tab shows setup instructions.

---

## TROUBLESHOOTING

- `streamlit not found` → Use `python -m streamlit run dashboard.py`
- `Port 8501 in use` → Use `streamlit run dashboard.py --server.port 8502`
- `netconvert not found` → SUMO not installed, dashboard still works in standalone mode
- `docker not found` → Docker Desktop not installed, dashboard uses in-memory DT
- `Ditto health check fails` → Wait longer, Ditto services need ~60s to fully start. Run `docker-compose ps` to check if all 6 services are running.
- `init_ditto.py fails` → Run `docker-compose logs gateway` to check gateway logs
- `Import errors` → Make sure terminal is in the project root directory (where dashboard.py is)

---

## WHAT WAS SET UP

```
Physical Layer (SUMO/Standalone)
        │ Vehicle positions, speeds
        ▼
   State Sync (every time step)
        │
        ▼
Digital Twin Layer ◄──── Eclipse Ditto (REST API on :8080)
   • Vehicle Twins         │
   • RSU Twins             ├── MongoDB (persistence)
   • MBS Twin              ├── 6 Docker services
   • Cloud Twin            └── Nginx reverse proxy
   • AoI Tracking
        │
        │ Exposed States
        ▼
GWO Optimization → Task Allocation → Execution
```
