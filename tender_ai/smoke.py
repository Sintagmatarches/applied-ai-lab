"""Probe a deployed private runtime from its network; never generates an answer."""
import argparse
import json
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Private runtime URL reachable from this runner")
    args = parser.parse_args()
    for path, expected in (("/live", "alive"), ("/ready", "ready")):
        with urlopen(args.base_url.rstrip("/") + path, timeout=12) as response:
            assert response.status == 200
            assert json.load(response)["status"] == expected
            assert response.headers.get("x-request-id")
    print("Liveness, readiness and request correlation verified")


if __name__ == "__main__":
    main()
