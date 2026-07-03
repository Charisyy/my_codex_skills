#!/usr/bin/env python3
"""Overlay translated text regions on an image without changing other pixels.

The script is intentionally small and generic. It covers rectangular text areas
with a background color sampled or specified by the caller, then redraws crisp
CJK text at high resolution before downsampling.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


def parse_color(value, image: Image.Image | None = None, box: list[int] | None = None):
    if value is None:
        if image is None or box is None:
            return None
        x1, y1, x2, y2 = box
        points = [
            (x1 + 1, y1 + 1),
            (x2 - 2, y1 + 1),
            (x1 + 1, y2 - 2),
            (x2 - 2, y2 - 2),
        ]
        pixels = [image.getpixel((max(0, min(image.width - 1, x)), max(0, min(image.height - 1, y)))) for x, y in points]
        return max(set(pixels), key=pixels.count)
    if isinstance(value, str) and value.startswith("#"):
        value = value.lstrip("#")
        if len(value) == 6:
            return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
        if len(value) == 8:
            return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4, 6))
    if isinstance(value, Iterable):
        return tuple(value)
    return value


def scaled_box(box: list[int], scale: int) -> tuple[int, int, int, int]:
    return tuple(int(round(v * scale)) for v in box)


def load_font(region: dict, spec: dict, scale: int) -> ImageFont.FreeTypeFont:
    font_path = region.get("font")
    if not font_path:
        font_path = spec.get("default_bold_font") if region.get("bold") else spec.get("default_font")
    if not font_path:
        raise ValueError("A font path is required via region.font, default_font, or default_bold_font.")
    return ImageFont.truetype(font_path, int(round(region.get("font_size", 16) * scale)))


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    explicit = text.split("\n")
    lines: list[str] = []
    for paragraph in explicit:
        current = ""
        for ch in paragraph:
            trial = current + ch
            bbox = draw.textbbox((0, 0), trial, font=font)
            if current and bbox[2] - bbox[0] > max_width:
                lines.append(current)
                current = ch
            else:
                current = trial
        lines.append(current)
    return lines


def draw_region(base: Image.Image, draw: ImageDraw.ImageDraw, region: dict, spec: dict, scale: int):
    box = region["box"]
    sx1, sy1, sx2, sy2 = scaled_box(box, scale)

    background = parse_color(region.get("background"), base, [sx1, sy1, sx2, sy2])
    if background is not None and region.get("cover", True):
        radius = int(round(region.get("radius", 0) * scale))
        if radius:
            draw.rounded_rectangle((sx1, sy1, sx2, sy2), radius=radius, fill=background)
        else:
            draw.rectangle((sx1, sy1, sx2, sy2), fill=background)

    font = load_font(region, spec, scale)
    fill = parse_color(region.get("fill", "#000000"))
    padding = int(round(region.get("padding", 0) * scale))
    line_spacing = int(round(region.get("line_spacing", 2) * scale))
    inner_w = max(1, sx2 - sx1 - 2 * padding)
    lines = wrap_lines(draw, region["text"], font, inner_w) if region.get("wrap", True) else region["text"].split("\n")

    metrics = [draw.textbbox((0, 0), line, font=font) for line in lines]
    heights = [bb[3] - bb[1] for bb in metrics]
    total_h = sum(heights) + line_spacing * max(0, len(lines) - 1)
    valign = region.get("valign", "middle")
    if valign == "top":
        y = sy1 + padding
    elif valign == "bottom":
        y = sy2 - padding - total_h
    else:
        y = sy1 + (sy2 - sy1 - total_h) // 2

    align = region.get("align", "center")
    for line, bb, height in zip(lines, metrics, heights):
        width = bb[2] - bb[0]
        if align == "left":
            x = sx1 + padding
        elif align == "right":
            x = sx2 - padding - width
        else:
            x = sx1 + (sx2 - sx1 - width) // 2
        draw.text((x, y - bb[1]), line, font=font, fill=fill)
        y += height + line_spacing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", help="Path to JSON replacement spec.")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    source = Path(spec["source"])
    output = Path(spec["output"])
    scale = int(spec.get("scale", 3))

    original = Image.open(source).convert("RGBA")
    work = original.resize((original.width * scale, original.height * scale), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(work)

    for region in spec["regions"]:
        draw_region(work, draw, region, spec, scale)

    result = work.resize(original.size, Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() in {".jpg", ".jpeg"}:
        result = result.convert("RGB")
    result.save(output)
    print(output)


if __name__ == "__main__":
    main()
