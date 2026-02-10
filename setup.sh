#!/bin/bash
# ═══════════════════════════════════════════════
# Setup Script for Digital Twin IoV Simulation
# ═══════════════════════════════════════════════
# Prerequisites:
#   - SUMO installed: sudo apt install sumo sumo-tools
#   - Python 3.8+
#   - pip install -r requirements.txt

set -e

echo "============================================="
echo " Digital Twin IoV - Setup"
echo "============================================="

# Check SUMO
if ! command -v netconvert &> /dev/null; then
    echo "[ERROR] SUMO not found. Install with:"
    echo "  sudo add-apt-repository ppa:sumo/stable"
    echo "  sudo apt update"
    echo "  sudo apt install sumo sumo-tools sumo-gui"
    exit 1
fi

echo "[1/3] Building SUMO network..."
cd sumo_files

netconvert \
    --node-files=network.nod.xml \
    --edge-files=network.edg.xml \
    --output-file=network.net.xml \
    --no-turnarounds=true

echo "  → network.net.xml created"
cd ..

echo "[2/3] Generating vehicle routes..."
python3 generate_routes.py

echo "[3/3] Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "============================================="
echo " Setup Complete!"
echo "============================================="
echo ""
echo " To run with SUMO GUI (recommended for demo):"
echo "   python3 run.py --sumo-gui"
echo ""
echo " To run with SUMO headless:"
echo "   python3 run.py --sumo"
echo ""
echo " To run without SUMO (built-in simulation):"
echo "   python3 run.py --sim"
echo ""
echo " Then open the Streamlit dashboard:"
echo "   streamlit run dashboard.py"
echo ""
