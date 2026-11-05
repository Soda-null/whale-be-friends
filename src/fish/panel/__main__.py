"""`python -m fish.panel`: start the panel and open it in the browser."""

from __future__ import annotations

import argparse

from fish.panel.server import DEFAULT_PORT, run


def main() -> None:
    ap = argparse.ArgumentParser(prog="fish.panel")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-open", action="store_true", help="do not open the browser")
    args = ap.parse_args()
    run(port=args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
