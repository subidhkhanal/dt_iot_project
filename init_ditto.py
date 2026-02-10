"""
Initialize Eclipse Ditto with all IoV Digital Twin entities.
Run this ONCE after starting Ditto with docker-compose up -d.

Creates:
  - 1 Policy (iov-policy)
  - 3 RSU Things (RSU_1, RSU_2, RSU_3)
  - 1 MBS Thing (MBS_1)
  - 1 Cloud Thing (CLOUD)
  - Vehicle Things are created dynamically during simulation
"""
import time
import sys
from ditto_client import DittoClient
import config as cfg


def wait_for_ditto(max_wait=60):
    """Wait for Ditto to be ready."""
    print("[Setup] Waiting for Eclipse Ditto to start...")
    start = time.time()
    while time.time() - start < max_wait:
        client = DittoClient()
        if client.is_connected():
            return client
        print(f"  Retrying in 5s... ({int(time.time()-start)}s elapsed)")
        time.sleep(5)
    print("[Setup] ERROR: Ditto did not start within timeout.")
    print("[Setup] Make sure Docker is running: docker-compose up -d")
    sys.exit(1)


def main():
    print("=" * 60)
    print(" Eclipse Ditto — IoV Digital Twin Initialization")
    print("=" * 60)

    # Wait for Ditto
    client = wait_for_ditto()

    # Create Policy
    print("\n[1/4] Creating IoV policy...")
    client.create_policy()

    # Create RSU Things
    print("\n[2/4] Creating RSU Digital Twins...")
    for rsu in cfg.RSU_CONFIG:
        success = client.create_thing(
            thing_id=rsu["id"],
            attributes={
                "type": "rsu",
                "x": rsu["x"],
                "y": rsu["y"],
                "coverage": rsu["coverage"],
                "capacity_mhz": rsu["capacity_mhz"],
                "cache_mb": rsu["cache_mb"],
            },
            features={
                "load": {"properties": {"current_load": 0, "utilization_pct": 0}},
                "serving": {"properties": {"vehicles_served": 0}},
                "cache": {"properties": {"cached_tasks": 0}},
                "sync": {"properties": {"last_sync": 0, "timestamp": 0}},
            }
        )
        status = "✓" if success else "✗"
        print(f"  {status} {rsu['id']} at ({rsu['x']}, {rsu['y']}) coverage={rsu['coverage']}m")

    # Create MBS Thing
    print("\n[3/4] Creating MBS Digital Twin...")
    success = client.create_thing(
        thing_id=cfg.MBS_CONFIG["id"],
        attributes={
            "type": "mbs",
            "x": cfg.MBS_CONFIG["x"],
            "y": cfg.MBS_CONFIG["y"],
            "coverage": cfg.MBS_CONFIG["coverage"],
            "capacity_mhz": cfg.MBS_CONFIG["capacity_mhz"],
            "cache_mb": cfg.MBS_CONFIG["cache_mb"],
        },
        features={
            "load": {"properties": {"current_load": 0}},
            "sync": {"properties": {"last_sync": 0, "timestamp": 0}},
        }
    )
    print(f"  {'✓' if success else '✗'} {cfg.MBS_CONFIG['id']} at ({cfg.MBS_CONFIG['x']}, {cfg.MBS_CONFIG['y']})")

    # Create Cloud Thing
    print("\n[4/4] Creating Cloud Digital Twin...")
    success = client.create_thing(
        thing_id="CLOUD",
        attributes={
            "type": "cloud",
            "capacity_ghz": cfg.CLOUD_CONFIG["capacity_ghz"],
            "power_mw": cfg.CLOUD_CONFIG["power_mw"],
        },
        features={
            "utilization": {"properties": {"current_pct": 0}},
            "sync": {"properties": {"last_sync": 0, "timestamp": 0}},
        }
    )
    print(f"  {'✓' if success else '✗'} CLOUD")

    # Verify
    print("\n" + "=" * 60)
    print(" Verification")
    print("=" * 60)
    things = client.list_things()
    print(f"  Total Things in Ditto: {len(things)}")
    for t in things:
        tid = t.get("thingId", "")
        ttype = t.get("attributes", {}).get("type", "?")
        print(f"    • {tid} (type: {ttype})")

    print("\n✓ Ditto initialization complete!")
    print("  You can now run: streamlit run dashboard.py")
    print(f"  Ditto API: http://localhost:8080/api/2/things")


if __name__ == "__main__":
    main()
