"""Parancssori értékelés — az OCR-lépés kihagyásával.

Példa:
    python -m motor.cli.ertekel --feladat "lnko(213, 200)" --helyes "1" --megoldas-fajl proba.txt
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from motor.grading import grade


def main(argv=None):
    p = argparse.ArgumentParser(description="Megoldás értékelése a feladatbank adataiból")
    p.add_argument("--feladat", required=True)
    p.add_argument("--helyes", required=True, help="a helyes megoldás / végeredmény")
    p.add_argument("--megoldas", help="a diák megoldása szövegként")
    p.add_argument("--megoldas-fajl", help="vagy fájlból")
    p.add_argument("--megjegyzes", help="a diák megjegyzése a felismerési hibáról")
    p.add_argument("--modell")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.megoldas_fajl:
        megoldas = Path(args.megoldas_fajl).read_text(encoding="utf-8")
    elif args.megoldas:
        megoldas = args.megoldas
    else:
        megoldas = sys.stdin.read()

    result = grade(args.feladat, args.helyes, megoldas, diak_megjegyzes=args.megjegyzes, modell=args.modell)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
