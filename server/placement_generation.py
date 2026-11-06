"""Generate a furniture layout.

Reads a JSON layout request on stdin and prints a single JSON line on stdout:
    the layout                           on success (exit code 0)
    {"error": "<message>"}               on invalid input (exit code 2) or when the furniture does not fit (exit code 3)

With --describe, prints the furniture types, presets, limits and form defaults instead.
See README.md for the request and response formats.
"""
import argparse
import json
import sys

from layout import InputError, PlacementError, describe, generate_layout


def emit(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--describe", action="store_true", help="print the options the frontend form needs")
    args = parser.parse_args()

    if args.describe:
        emit(describe())
        return 0

    try:
        emit(generate_layout(json.load(sys.stdin)))
    except json.JSONDecodeError:
        emit({"error": "Request body is not valid JSON"})
        return 2
    except InputError as e:
        emit({"error": str(e)})
        return 2
    except PlacementError as e:
        emit({"error": str(e)})
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
