from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute SHA-256 over exact result bytes.")
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    print(hashlib.sha256(args.result.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()

