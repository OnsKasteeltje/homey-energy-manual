#!/usr/bin/env python3

"""Read-only local probe for existing thermal signal sources.

Searches known EMS runtime/repository/data locations for textual references to already
registered thermal metrics and related Honeywell/Quatt/CV terms. It does not call Homey,
does not open network connections and does not write files.
"""

from pathlib import Path

ROOTS = [
    Path('/home/jeroen/ems/runtime'),
    Path('/home/jeroen/ems/repo/homey-energy-manual'),
    Path('/home/jeroen/ems/data'),
]

TERMS = [
    'room_temperature_c',
    'room_setpoint_c',
    'heating_on',
    'measure_temperature',
    'target_temperature',
    'thermostat',
    'honeywell',
    'quatt',
    'cv_assist',
    'vaillant',
]

TEXT_SUFFIXES = {
    '.py', '.js', '.mjs', '.cjs', '.json', '.md', '.txt', '.yaml', '.yml', '.service', '.timer', '.env'
}

MAX_BYTES = 2_000_000


def eligible(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() in {'.sqlite', '.db', '.parquet', '.gz', '.zip', '.png', '.jpg', '.jpeg', '.webp'}:
        return False
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.name in {'Dockerfile', 'Makefile'}


def main():
    hits = []
    scanned = 0

    for root in ROOTS:
        if not root.exists():
            continue
        for path in root.rglob('*'):
            try:
                if not eligible(path):
                    continue
                if path.stat().st_size > MAX_BYTES:
                    continue
                text = path.read_text(errors='ignore')
            except (OSError, UnicodeError):
                continue

            scanned += 1
            lower = text.lower()
            matched = [term for term in TERMS if term.lower() in lower]
            if matched:
                rel = str(path)
                hits.append((rel, matched))

    print('=== LOCAL THERMAL SOURCE REFERENCES ===')
    for path, matched in sorted(hits):
        print(f'{path}: {", ".join(matched)}')

    print('\n=== SUMMARY ===')
    print(f'scanned_text_files={scanned}')
    print(f'matching_files={len(hits)}')
    print('PASS: local filesystem only; no Homey API calls; no network; no writes.')


if __name__ == '__main__':
    main()
