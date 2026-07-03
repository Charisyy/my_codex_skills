#!/usr/bin/env python3
"""Redraw translated text regions while preserving the rest of the image.

The script edits only the rectangles described in a JSON spec. Each rectangle is
rendered at high resolution, downsampled, and pasted back into the original, so
pixels outside replacement boxes remain unchanged.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


def parse_color(value, fallback=None):
    if value is None or value == "sample":
        return fallback
    if isinstance(value, str) and value.startswith("#"):
        value = value.lstrip("#")
        if len(value) == 6:
            return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
        if len(value) == 8:
            return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4, 6))
    if isinstance(value, Iterable) and not isinstance(value, str):
        return tuple(value)
    return value


def sample_background(crop: Image.Image, inset: int = 2):
    """Return a robust dominant border color for flat UI backgrounds."""
    w, h = crop.size
    if w == 0 or h == 0:
        return (255, 255, 255, 255)
    pts = []
    xs = range(max(0, inset), max(1, w - inset))
    ys = range(max(0, inset), max(1, h - inset))
    for x in xs:
        pts.append((x, min(h - 1, inset)))
        pts.append((x, max(0, h - 1 - inset)))
    for y in ys:
        pts.append((min(w - 1, inset), y))
        pts.append((max(0, w - 1 - inset), y))
    pixels = [crop.getpixel(p) for p in pts]
    return Counter(pixels).most_common(1)[0][0]


def scaled_box(box: list[int], scale: int) -> tuple[int, int, int, int]:
    return tuple(int(round(v * scale)) for v in box)


def font_path_for(region: dict, spec: dict):
    if region.get("font"):
        return region["font"]
    if region.get("bold") and spec.get("default_bold_font"):
        return spec["default_bold_font"]
    if spec.get("default_font"):
        return spec["default_font"]
    raise ValueError("A font path is required via region.font, default_font, or default_bold_font.")


def load_font(path: str, size: int, scale: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, max(1, int(round(size * scale))))


def text_bbox(draw: ImageDraw.ImageDraw, text: str, font, stroke_width: int = 0):
    return draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, stroke_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for ch in paragraph:
            trial = current + ch
            bb = text_bbox(draw, trial, font, stroke_width)
            if current and bb[2] - bb[0] > max_width:
                lines.append(current)
                current = ch
            else:
                current = trial
        lines.append(current)
    return lines


def measure_lines(draw, lines, font, line_spacing, stroke_width):
    boxes = [text_bbox(draw, line, font, stroke_width) for line in lines]
    widths = [bb[2] - bb[0] for bb in boxes]
    heights = [bb[3] - bb[1] for bb in boxes]
    total_h = sum(heights) + line_spacing * max(0, len(lines) - 1)
    return boxes, widths, heights, total_h


def choose_font_and_lines(draw, region, spec, scale, inner_w, inner_h, stroke_width):
    font_path = font_path_for(region, spec)
    requested = int(region.get("font_size", 16))
    min_size = int(region.get("min_font_size", max(8, math.floor(requested * 0.72))))
    line_spacing_base = int(region.get("line_spacing", 2))
    wrap = region.get("wrap", True)
    fit = region.get("fit", "shrink")

    for size in range(requested, min_size - 1, -1):
        font = load_font(font_path, size, scale)
        line_spacing = int(round(line_spacing_base * scale))
        lines = wrap_lines(draw, region["text"], font, inner_w, stroke_width) if wrap else region["text"].split("\n")
        boxes, widths, heights, total_h = measure_lines(draw, lines, font, line_spacing, stroke_width)
        if fit != "shrink" or (max(widths or [0]) <= inner_w and total_h <= inner_h):
            return font, lines, boxes, widths, heights, total_h, line_spacing, size

    font = load_font(font_path, min_size, scale)
    line_spacing = int(round(line_spacing_base * scale))
    lines = wrap_lines(draw, region["text"], font, inner_w, stroke_width) if wrap else region["text"].split("\n")
    boxes, widths, heights, total_h = measure_lines(draw, lines, font, line_spacing, stroke_width)
    if region.get("strict_fit") and (max(widths or [0]) > inner_w or total_h > inner_h):
        raise ValueError(f"Text does not fit region {region.get('id', region.get('box'))}; enlarge box or reduce font_size.")
    return font, lines, boxes, widths, heights, total_h, line_spacing, min_size


def render_region(original: Image.Image, region: dict, spec: dict, scale: int):
    x1, y1, x2, y2 = region["box"]
    crop = original.crop((x1, y1, x2, y2)).convert("RGBA")
    patch = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(patch)

    bg = parse_color(region.get("background", "sample"), sample_background(crop))
    if region.get("cover", True):
        radius = int(round(region.get("radius", 0) * scale))
        rect = (0, 0, patch.width, patch.height)
        if radius:
            draw.rounded_rectangle(rect, radius=radius, fill=bg)
        else:
            draw.rectangle(rect, fill=bg)

    padding = region.get("padding", 0)
    if isinstance(padding, int):
        pad_l = pad_t = pad_r = pad_b = int(round(padding * scale))
    else:
        pad_l, pad_t, pad_r, pad_b = [int(round(v * scale)) for v in padding]
    inner_w = max(1, patch.width - pad_l - pad_r)
    inner_h = max(1, patch.height - pad_t - pad_b)

    stroke_width = int(round(region.get("stroke_width", 0) * scale))
    font, lines, boxes, widths, heights, total_h, line_spacing, used_size = choose_font_and_lines(
        draw, region, spec, scale, inner_w, inner_h, stroke_width
    )
    fill = parse_color(region.get("fill", "#000000"))
    stroke_fill = parse_color(region.get("stroke_fill", "#ffffff"))

    valign = region.get("valign", "middle")
    if valign == "top":
        y = pad_t
    elif valign == "bottom":
        y = patch.height - pad_b - total_h
    else:
        y = pad_t + (inner_h - total_h) // 2

    align = region.get("align", "center")
    for line, bb, width, height in zip(lines, boxes, widths, heights):
        if align == "left":
            x = pad_l
        elif align == "right":
            x = patch.width - pad_r - width
        else:
            x = pad_l + (inner_w - width) // 2
        draw.text((x - bb[0], y - bb[1]), line, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        y += height + line_spacing

    resample = Image.Resampling.LANCZOS if region.get("antialias", True) else Image.Resampling.NEAREST
    out_patch = patch.resize(crop.size, resample)
    return (x1, y1), out_patch, used_size


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", help="Path to JSON replacement spec.")
    parser.add_argument("--report", action="store_true", help="Print per-region font fitting details.")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    source = Path(spec["source"])
    output = Path(spec["output"])
    scale = int(spec.get("scale", 3))

    result = Image.open(source).convert("RGBA")
    report = []
    for i, region in enumerate(spec["regions"]):
        pos, patch, used_size = render_region(result, region, spec, scale)
        result.paste(patch, pos)
        report.append({"index": i, "id": region.get("id"), "font_size": used_size, "box": region["box"]})

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() in {".jpg", ".jpeg"}:
        result = result.convert("RGB")
    result.save(output)
    print(output)
    if args.report:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
