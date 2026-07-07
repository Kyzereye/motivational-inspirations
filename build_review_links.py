#!/usr/bin/env python3
"""Create review/ symlinks in queue_backup.txt order for caption editing."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REVIEW_DIR = BASE_DIR / 'review'
IMAGES_DIR = BASE_DIR / 'images'
QUEUE_BACKUP = BASE_DIR / 'list' / 'queue_backup.txt'


def main():
    if REVIEW_DIR.exists():
        for path in REVIEW_DIR.iterdir():
            path.unlink()
    else:
        REVIEW_DIR.mkdir()

    lines = [
        line.strip()
        for line in QUEUE_BACKUP.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]

    created = 0
    missing = []
    for index, name in enumerate(lines, start=1):
        source = IMAGES_DIR / name
        if not source.exists():
            missing.append(name)
            continue
        link = REVIEW_DIR / f'{index:04d}_{name}'
        link.symlink_to(Path('..') / 'images' / name)
        created += 1

    print(f'Created {created} symlinks in {REVIEW_DIR}')
    if missing:
        print(f'Skipped {len(missing)} missing from images/:')
        for name in missing:
            print(f'  {name}')


if __name__ == '__main__':
    main()
