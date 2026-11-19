"""Open the dashboard served by a running OpenBuddy event bridge."""

import argparse

from pc.opencode import discovery_path, load_discovery
from pc.webui import open_dashboard


def main():
    parser = argparse.ArgumentParser(description="Open the running OpenBuddy bridge dashboard")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser")
    args = parser.parse_args()
    try:
        bridge = load_discovery(discovery_path())
    except (OSError, ValueError):
        parser.exit(1, "No OpenBuddy bridge is running; start `python -m pc.opencode` first.\n")
    url = "http://127.0.0.1:%d/" % bridge["port"]
    if args.no_browser:
        print("OpenBuddy dashboard is available at", url)
        return
    if not open_dashboard(url, bridge["token"]):
        parser.exit(1, "Could not open a browser; visit %s after starting the bridge.\n" % url)
    print("Opened OpenBuddy dashboard at", url)


if __name__ == "__main__":
    main()
