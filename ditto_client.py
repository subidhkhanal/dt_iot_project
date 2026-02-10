"""
Eclipse Ditto REST API Client
Manages Digital Twin "Things" in Ditto for IoV components.

Ditto API: http://localhost:8080/api/2/things/{thingId}

Each IoV component (Vehicle, RSU, MBS, Cloud) is a Ditto "Thing" with:
  - thingId:    org.eclipse.ditto:RSU_1
  - policyId:   org.eclipse.ditto:iov-policy
  - attributes: static properties (position, coverage, capacity)
  - features:   dynamic state (load, speed, connected_rsu, aoi)
"""
import requests
import json
import time

DITTO_BASE_URL = "http://localhost:8080"
DITTO_API = f"{DITTO_BASE_URL}/api/2"
DITTO_AUTH = ("ditto", "ditto")  # default dummy auth
NAMESPACE = "org.eclipse.ditto"
POLICY_ID = f"{NAMESPACE}:iov-policy"

HEADERS = {"Content-Type": "application/json"}


class DittoClient:
    """Client for Eclipse Ditto Digital Twin platform."""

    def __init__(self, base_url=None):
        self.base_url = base_url or DITTO_API
        self.auth = DITTO_AUTH
        self.connected = False
        self._check_connection()

    def _check_connection(self):
        """Check if Ditto is reachable."""
        try:
            r = requests.get(f"{DITTO_BASE_URL}/health", timeout=5)
            self.connected = r.status_code == 200
            if self.connected:
                print("[Ditto] ✓ Connected to Eclipse Ditto")
            else:
                print(f"[Ditto] ✗ Health check returned {r.status_code}")
        except requests.exceptions.ConnectionError:
            self.connected = False
            print("[Ditto] ✗ Cannot reach Ditto at localhost:8080")
            print("[Ditto]   Make sure Docker is running: docker-compose up -d")
        except Exception as e:
            self.connected = False
            print(f"[Ditto] ✗ Connection error: {e}")

    def is_connected(self):
        return self.connected

    # ─────────────────────────────────────────
    # Policy Management
    # ─────────────────────────────────────────
    def create_policy(self):
        """Create the IoV policy that allows full CRUD on all things."""
        policy = {
            "policyId": POLICY_ID,
            "entries": {
                "owner": {
                    "subjects": {
                        "nginx:ditto": {"type": "nginx basic auth user"}
                    },
                    "resources": {
                        "thing:/": {"grant": ["READ", "WRITE"], "revoke": []},
                        "policy:/": {"grant": ["READ", "WRITE"], "revoke": []},
                        "message:/": {"grant": ["READ", "WRITE"], "revoke": []}
                    }
                }
            }
        }
        url = f"{self.base_url}/policies/{POLICY_ID}"
        r = requests.put(url, json=policy, headers=HEADERS, auth=self.auth)
        if r.status_code in [200, 201, 204]:
            print(f"[Ditto] Policy created: {POLICY_ID}")
            return True
        else:
            print(f"[Ditto] Policy creation: {r.status_code} - {r.text[:200]}")
            return r.status_code == 409  # already exists is OK

    # ─────────────────────────────────────────
    # Thing CRUD
    # ─────────────────────────────────────────
    def create_thing(self, thing_id, attributes=None, features=None):
        """Create a Digital Twin 'Thing' in Ditto."""
        full_id = f"{NAMESPACE}:{thing_id}"
        thing = {
            "thingId": full_id,
            "policyId": POLICY_ID,
            "attributes": attributes or {},
            "features": features or {}
        }
        url = f"{self.base_url}/things/{full_id}"
        r = requests.put(url, json=thing, headers=HEADERS, auth=self.auth)
        if r.status_code in [200, 201, 204]:
            return True
        elif r.status_code == 409:
            return True  # already exists
        else:
            print(f"[Ditto] Create thing {thing_id}: {r.status_code} - {r.text[:200]}")
            return False

    def update_features(self, thing_id, features):
        """Update the dynamic features of a Thing."""
        full_id = f"{NAMESPACE}:{thing_id}"
        url = f"{self.base_url}/things/{full_id}/features"
        r = requests.put(url, json=features, headers=HEADERS, auth=self.auth)
        return r.status_code in [200, 201, 204]

    def update_feature(self, thing_id, feature_name, properties):
        """Update a single feature of a Thing."""
        full_id = f"{NAMESPACE}:{thing_id}"
        url = f"{self.base_url}/things/{full_id}/features/{feature_name}/properties"
        r = requests.put(url, json=properties, headers=HEADERS, auth=self.auth)
        return r.status_code in [200, 201, 204]

    def get_thing(self, thing_id):
        """Retrieve a Thing from Ditto."""
        full_id = f"{NAMESPACE}:{thing_id}"
        url = f"{self.base_url}/things/{full_id}"
        r = requests.get(url, headers=HEADERS, auth=self.auth)
        if r.status_code == 200:
            return r.json()
        return None

    def get_feature(self, thing_id, feature_name):
        """Get a specific feature of a Thing."""
        full_id = f"{NAMESPACE}:{thing_id}"
        url = f"{self.base_url}/things/{full_id}/features/{feature_name}"
        r = requests.get(url, headers=HEADERS, auth=self.auth)
        if r.status_code == 200:
            return r.json()
        return None

    def delete_thing(self, thing_id):
        """Delete a Thing from Ditto."""
        full_id = f"{NAMESPACE}:{thing_id}"
        url = f"{self.base_url}/things/{full_id}"
        r = requests.delete(url, headers=HEADERS, auth=self.auth)
        return r.status_code in [200, 204]

    def list_things(self, filter_str=None):
        """List all Things, optionally filtered."""
        url = f"{self.base_url}/search/things"
        params = {}
        if filter_str:
            params["filter"] = filter_str
        r = requests.get(url, params=params, headers=HEADERS, auth=self.auth)
        if r.status_code == 200:
            return r.json().get("items", [])
        return []

    # ─────────────────────────────────────────
    # Bulk Operations
    # ─────────────────────────────────────────
    def update_vehicle_twin(self, vehicle_id, x, y, speed, connected_rsu, num_tasks, sync_time):
        """Update a vehicle's digital twin in Ditto."""
        features = {
            "position": {
                "properties": {
                    "x": round(x, 1),
                    "y": round(y, 1)
                }
            },
            "mobility": {
                "properties": {
                    "speed_kmh": round(speed, 1)
                }
            },
            "connectivity": {
                "properties": {
                    "connected_rsu": connected_rsu
                }
            },
            "tasks": {
                "properties": {
                    "count": num_tasks
                }
            },
            "sync": {
                "properties": {
                    "last_sync": round(sync_time, 3),
                    "timestamp": time.time()
                }
            }
        }
        return self.update_features(vehicle_id, features)

    def update_rsu_twin(self, rsu_id, load, vehicles_served, utilization_pct, cached_tasks, sync_time):
        """Update an RSU's digital twin in Ditto."""
        features = {
            "load": {
                "properties": {
                    "current_load": load,
                    "utilization_pct": round(utilization_pct, 1)
                }
            },
            "serving": {
                "properties": {
                    "vehicles_served": vehicles_served
                }
            },
            "cache": {
                "properties": {
                    "cached_tasks": cached_tasks
                }
            },
            "sync": {
                "properties": {
                    "last_sync": round(sync_time, 3),
                    "timestamp": time.time()
                }
            }
        }
        return self.update_features(rsu_id, features)

    def get_all_vehicle_states(self):
        """Retrieve all vehicle twins from Ditto."""
        things = self.list_things(
            filter_str='eq(attributes/type,"vehicle")'
        )
        vehicles = []
        for t in things:
            tid = t.get("thingId", "").replace(f"{NAMESPACE}:", "")
            attrs = t.get("attributes", {})
            feats = t.get("features", {})
            vehicles.append({
                "id": tid,
                "x": feats.get("position", {}).get("properties", {}).get("x", 0),
                "y": feats.get("position", {}).get("properties", {}).get("y", 0),
                "speed": feats.get("mobility", {}).get("properties", {}).get("speed_kmh", 0),
                "connected_rsu": feats.get("connectivity", {}).get("properties", {}).get("connected_rsu", "N/A"),
                "num_tasks": feats.get("tasks", {}).get("properties", {}).get("count", 0),
                "last_sync": feats.get("sync", {}).get("properties", {}).get("last_sync", 0),
            })
        return vehicles

    def get_all_rsu_states(self):
        """Retrieve all RSU twins from Ditto."""
        things = self.list_things(
            filter_str='eq(attributes/type,"rsu")'
        )
        rsus = []
        for t in things:
            tid = t.get("thingId", "").replace(f"{NAMESPACE}:", "")
            attrs = t.get("attributes", {})
            feats = t.get("features", {})
            rsus.append({
                "id": tid,
                "x": attrs.get("x", 0),
                "y": attrs.get("y", 0),
                "coverage": attrs.get("coverage", 0),
                "load": feats.get("load", {}).get("properties", {}).get("current_load", 0),
                "vehicles_served": feats.get("serving", {}).get("properties", {}).get("vehicles_served", 0),
                "utilization_pct": feats.get("load", {}).get("properties", {}).get("utilization_pct", 0),
                "cached_tasks": feats.get("cache", {}).get("properties", {}).get("cached_tasks", 0),
            })
        return rsus
