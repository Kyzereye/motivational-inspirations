#!/usr/bin/env python3
import argparse
import os
import re
import sys

import pytesseract
from PIL import Image, ImageEnhance

from caption_lib import (
    build_caption,
    load_captions,
    parse_author_from_filename,
    save_captions,
    should_regenerate_caption,
    slug_to_title,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, 'images')
LIST_DIR = os.path.join(BASE_DIR, 'list')

PNG_TAGLINE_RE = re.compile(
    r'motivational inspiration\s*[-–—]\s*\w+|inspiration\s*[-–—]\s*\w+\s*$',
    re.IGNORECASE,
)

FOOTER_RE = re.compile(
    r'inspirational motivation|motivational inspiration|ownership|keep moving forward',
    re.IGNORECASE,
)
HANDLE_RE = re.compile(r'@\S+')
WATERMARK_RE = re.compile(r'\bt?nspirational\s+motivation\b', re.IGNORECASE)


def read_filename_list(path):
    names = []
    if not os.path.exists(path):
        return names
    with open(path, encoding='utf-8') as handle:
        for line in handle:
            name = line.strip()
            if name:
                names.append(name)
    return names


def collect_filenames():
    filenames = set()
    filenames.update(read_filename_list(os.path.join(LIST_DIR, 'queue.txt')))
    filenames.update(read_filename_list(os.path.join(LIST_DIR, 'posted_log.txt')))
    return sorted(filenames)


def prepare_image(image):
    if max(image.size) > 1800:
        image = image.copy()
        image.thumbnail((1800, 1800))
    return image.convert('RGB')


def score_ocr_text(text):
    cleaned = clean_ocr_text(text)
    if not cleaned:
        return 0
    words = re.findall(r'[a-zA-Z]{2,}', cleaned)
    if len(words) < 2:
        return len(words)
    return sum(len(word) for word in words) + len(words) * 3


def clean_ocr_text(text):
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if FOOTER_RE.search(stripped):
            continue
        if len(stripped) <= 2:
            continue
        lines.append(stripped)
    return '\n'.join(lines).strip()


def normalize_quote(quote):
    quote = WATERMARK_RE.sub(' ', quote)
    quote = FOOTER_RE.sub(' ', quote)
    quote = HANDLE_RE.sub(' ', quote)
    quote = ' '.join(quote.split())
    return quote.strip()


def extract_best_phrase(quote):
    candidates = [quote]
    for pattern in (
        r'[A-Z][A-Z\'\-]*(?:\s+[A-Z][A-Z\'\-]*){2,}',
        r"[A-Za-z]{3,}(?:\s+[A-Za-z]{2,}){2,}",
    ):
        for match in re.finditer(pattern, quote):
            candidates.append(match.group(0))

    def rank(text):
        words = re.findall(r"[A-Za-z']+", text)
        if len(words) < 3:
            return (0, 0, 0)
        long_words = sum(1 for word in words if len(word) >= 3)
        ratio = long_words / len(words)
        letters = sum(char.isalpha() for char in text)
        if ratio < 0.5:
            return (0, 0, 0)
        return (long_words, letters, ratio)

    return max(candidates, key=rank).strip()


def polish_quote(quote):
    quote = normalize_quote(quote)
    if not quote:
        return ''
    quote = extract_best_phrase(quote)
    quote = normalize_quote(quote)
    words = re.findall(r"[A-Za-z']+", quote)
    if len(words) < 3:
        return ''
    return quote


def line_quality(line):
    letters = sum(char.isalpha() for char in line)
    if letters < 3:
        return 0
    return letters / max(len(line), 1)


def extract_quote_from_ocr(text, author):
    cleaned = clean_ocr_text(text)
    if not cleaned:
        return ''

    parts = [part.strip() for part in re.split(r'\n{2,}', cleaned) if part.strip()]
    if not parts:
        parts = [line.strip() for line in cleaned.splitlines() if line.strip()]

    if author:
        author_lower = author.lower()
        parts = [
            part for part in parts
            if not (author_lower in part.lower() and len(part.split()) <= 4)
        ] or parts

    if len(parts) == 1:
        quote = ' '.join(parts[0].split())
    elif len(parts[0].split()) <= 6 and len(parts) > 1:
        quote = ' '.join(parts[1:])
    else:
        ranked = sorted(parts, key=line_quality, reverse=True)
        quote = ranked[0] if ranked and line_quality(ranked[0]) >= 0.35 else ' '.join(parts)

    return polish_quote(quote)


def extract_png_quote(ocr_text, filename):
    title = slug_to_title(filename)
    lines = []
    for line in clean_ocr_text(ocr_text).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if PNG_TAGLINE_RE.search(stripped):
            continue
        lines.append(stripped)

    title_lower = title.lower()
    body_lines = []
    title_found = False
    for line in lines:
        line_lower = line.lower()
        if not title_found and title_lower in line_lower:
            title_found = True
            remainder = line_lower.split(title_lower, 1)[1].strip(' .-—')
            if remainder:
                body_lines.append(line[line.lower().index(title_lower) + len(title_lower):].strip(' .-—'))
            continue
        if title_found:
            body_lines.append(line)

    if not title_found and lines:
        first = lines[0]
        if first.lower().startswith(title_lower):
            remainder = first[len(title):].strip(' .-—')
            if remainder:
                body_lines.append(remainder)
            body_lines.extend(lines[1:])
        else:
            body_lines = lines

    body = ' '.join(' '.join(body_lines).split()).strip()
    body = PNG_TAGLINE_RE.sub('', body).strip(' .-—')
    if not body:
        flat = ' '.join(' '.join(lines).split())
        if flat.lower().startswith(title_lower):
            body = flat[len(title):].strip(' .-—')
        else:
            body = flat

    if not body:
        return f'{title}.'
    return f'{title}.\n{body}'


def ocr_image(path):
    with Image.open(path) as image:
        rgb = prepare_image(image)
        gray = ImageEnhance.Contrast(rgb.convert('L')).enhance(1.5)
        attempts = [
            (rgb, 6),
            (rgb, 11),
            (rgb, 3),
            (gray, 6),
        ]
        best_text = ''
        best_score = 0
        for variant, psm in attempts:
            text = pytesseract.image_to_string(variant, config=f'--psm {psm}')
            score = score_ocr_text(text)
            if score > best_score:
                best_score = score
                best_text = text
        return best_text


def extract_quote_and_author(path, filename):
    author = parse_author_from_filename(filename)
    try:
        ocr_text = ocr_image(path)
    except OSError as exc:
        print(f'OCR failed for {filename}: {exc}', file=sys.stderr)
        ocr_text = ''

    if filename.lower().endswith('.png'):
        quote = extract_png_quote(ocr_text, filename)
        return quote, author

    quote = extract_quote_from_ocr(ocr_text, author)
    if not quote:
        if author:
            quote = ''
        elif filename.lower().endswith('.png'):
            quote = slug_to_title(filename)
        else:
            quote = ''
    elif quote:
        quote = ' '.join(quote.split())
    return quote, author


def generate_for_filename(filename, captions, force=False):
    path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(path):
        print(f'Missing image: {filename}', file=sys.stderr)
        return False

    if filename.startswith('topo3_'):
        return False

    existing = captions.get(filename, {})
    old_caption = (existing.get('caption') or '').strip()
    quote, _author = extract_quote_and_author(path, filename)

    if filename.lower().endswith('.png'):
        if not quote:
            return False
        if should_regenerate_caption(quote, old_caption) or force:
            caption = build_caption(quote, filename)
        else:
            caption = old_caption
        captions[filename] = {'quote': quote, 'caption': caption}
        return True

    if not quote:
        return False
    captions[filename] = {
        'quote': quote,
        'caption': build_caption(quote, filename),
    }
    return True


def should_skip(filename, existing, force):
    if filename.startswith('topo3_'):
        return True
    if force:
        return False
    if filename.lower().endswith('.png'):
        return False
    return has_quote(existing)


def has_quote(entry):
    return bool((entry.get('quote') or '').strip())


def main():
    parser = argparse.ArgumentParser(description='Generate captions.json from queue images.')
    parser.add_argument(
        '--force',
        action='store_true',
        help='Regenerate captions even if an entry already exists.',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='Process only the first N filenames (0 = all).',
    )
    parser.add_argument(
        '--prefix',
        action='append',
        default=[],
        help='Only process filenames starting with this prefix (repeatable).',
    )
    args = parser.parse_args()

    filenames = collect_filenames()
    if args.prefix:
        filenames = [
            filename
            for filename in filenames
            if any(filename.startswith(prefix) for prefix in args.prefix)
        ]
    if args.limit:
        filenames = filenames[: args.limit]

    captions = load_captions(BASE_DIR)
    total = len(filenames)
    created = 0
    skipped = 0

    for index, filename in enumerate(filenames, start=1):
        existing = captions.get(filename, {})
        if should_skip(filename, existing, args.force):
            skipped += 1
            continue
        if generate_for_filename(filename, captions, force=args.force):
            created += 1
        if index % 10 == 0 or index == total:
            save_captions(captions, BASE_DIR)
            print(f'Progress: {index}/{total} ({created} created, {skipped} skipped)')

    save_captions(captions, BASE_DIR)
    print(f'Done. {created} created, {skipped} skipped, {len(captions)} total in captions.json')


if __name__ == '__main__':
    main()
