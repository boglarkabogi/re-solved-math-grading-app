"""Parancssori értékelés — az OCR-lépés kihagyásával.

Példa:
    python -m motor.cli.ertekel --feladat "lnko(213, 200)" --helyes "1" --megoldas-fajl proba.txt
"""

import argparse
import json
import sys
from pathlib import Path

from motor.grading import ertekel


def main(argv=None):
    p = argparse.ArgumentParser(description="Megoldás értékelése a feladatbank adataiból")
    p.add_argument("--feladat", required=True)
    p.add_argument("--helyes", required=True, help="a helyes megoldás / végeredmény")
    p.add_argument("--megoldas", help="a diák megoldása szövegként")
    p.add_argument("--megoldas-fajl", help="vagy fájlból")
    p.add_argument("--temakor")
    p.add_argument("--modell")
    args = p.parse_args(argv)

    if args.megoldas_fajl:
        megoldas = Path(args.megoldas_fajl).read_text(encoding="utf-8")
    elif args.megoldas:
        megoldas = args.megoldas
    else:
        megoldas = sys.stdin.read()

    eredmeny = ertekel(args.feladat, args.helyes, megoldas, temakor=args.temakor, modell=args.modell)
    print(json.dumps(eredmeny, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
