---
name: image-s2t
description: Convert simplified Chinese text inside images to traditional Chinese while preserving all other visual elements with production-quality clarity. Use when the user asks to translate image text from 简体中文/简体字 to 繁体中文/繁体字, especially for screenshots, flowcharts, posters, diagrams, UI captures, scanned images, GIF/video frames, or requests that require unchanged layout, complete elements, sharp text, lossless-looking output, or “其他不要改变”.
---

# Image S2T

## Mission

Convert only simplified Chinese text in an image to traditional Chinese. Preserve canvas size, layout, non-text pixels, colors, icons, lines, arrows, backgrounds, shadows, spacing, file type intent, and visual hierarchy unless the user explicitly requests otherwise.

## Quality Bar

- Treat this as image restoration plus typesetting, not casual translation.
- Do not paraphrase, embellish, summarize, or improve wording. Convert script only.
- Keep numbers, Latin text, formulas, product names, file names, units, and punctuation intent unchanged unless script conversion clearly requires a Chinese punctuation variant.
- Do not use generative image editing for text replacement when deterministic redrawing can work.
- Prefer local redrawing with real fonts and exact coordinates. Text must be crisp at 100% zoom.
- Preserve image dimensions. Do not crop, scale, compress heavily, or change color mode unless needed by the requested output format.
- Save a new output file. Never overwrite the source unless the user explicitly asks.

## Decision Tree

1. **Flat UI screenshot, diagram, card, flowchart, slide, poster with simple regions**
   - Use coordinate-based cover-and-redraw.
   - Prefer `scripts/overlay_text_regions.py` for rectangular text regions.

2. **Complex background behind text**
   - First try localized clone/inpaint only inside the text bounding box.
   - Redraw text deterministically after removing the original glyphs.
   - Do not let inpainting change surrounding objects.

3. **Repeated frames in GIF/video**
   - Extract frames, process only frames containing the text or build reusable coordinates.
   - Reassemble with original frame count, frame order, timing, loop setting, and dimensions.
   - Validate representative frames and timing.

4. **Very small text or dense typography**
   - Use a CJK-capable font close to the original.
   - Increase render scale, tune font size, and inspect at 100% and zoomed views.
   - If exact fit is impossible, slightly reduce font size before changing layout.

## Workflow

1. Inspect the source image.
   - Record width, height, file type, and all visible simplified Chinese text.
   - Identify each text bounding box. Include enough padding to fully cover old glyph antialiasing, but avoid covering nearby icons, borders, arrows, or shadows.
   - Sample local colors from the original region instead of guessing when backgrounds are flat.

2. Transcribe exactly.
   - Manual transcription is preferred for short screenshots and diagrams.
   - OCR may be used only as a draft. Correct OCR against the image before drawing.
   - Build a source-to-target checklist for every text block.

3. Convert to traditional Chinese.
   - Prefer OpenCC (`s2t` for general traditional, `s2tw` if the user expects Taiwan wording).
   - If OpenCC is unavailable, convert carefully and verify phrase by phrase.
   - Avoid locale vocabulary rewrites unless the user asks. For example, do not change meaning, tone, or business terminology just because another word sounds more natural.

4. Recreate typography.
   - Match original visual weight: regular vs bold, approximate family, size, color, alignment, and line spacing.
   - Use CJK fonts such as Microsoft YaHei, Microsoft JhengHei, SimHei, Noto Sans CJK, Source Han Sans, PingFang, or system equivalents.
   - For white-on-color or tiny text, consider stroke only if the original has an outline or if it is necessary to match antialiasing.
   - Use shrink-to-fit before changing line breaks. Preserve explicit line breaks when visible in the source.

5. Render locally.
   - Preserve pixels outside edited regions whenever possible.
   - For UI boxes/cards, redraw or cover only the interior text area if borders and shadows should remain.
   - For complete shape reconstruction, use exact coordinates, radius, fill, outline, and shadow matching the original.

6. Validate before delivery.
   - Open the output visually at normal size and zoomed size.
   - Confirm no simplified Chinese remains in edited text.
   - Confirm every non-text element remains complete and aligned.
   - Confirm no mojibake, question marks, clipped glyphs, overflow, fuzzy text, unexpected resizing, or background scars.
   - For strict work, compare dimensions and file properties. For GIF/video, compare frame count, timing, and loop metadata.

## Helper Script

Use `scripts/overlay_text_regions.py` for deterministic rectangular replacements. The script edits only the specified rectangles, renders at high resolution, then pastes patches back into the original so pixels outside replacement boxes remain unchanged.

Run:

```bash
python scripts/overlay_text_regions.py spec.json --report
```

Spec example:

```json
{
  "source": "C:/path/input.png",
  "output": "C:/path/output.png",
  "default_font": "C:/Windows/Fonts/msyh.ttc",
  "default_bold_font": "C:/Windows/Fonts/msyhbd.ttc",
  "scale": 4,
  "regions": [
    {
      "id": "title",
      "box": [52, 28, 390, 66],
      "text": "辦公用品數據篩選與計算流程",
      "font_size": 25,
      "min_font_size": 20,
      "bold": true,
      "fill": "#0e1c34",
      "background": "#f6f8fb",
      "padding": [0, 0, 0, 0],
      "align": "left",
      "valign": "middle",
      "fit": "shrink",
      "strict_fit": true
    }
  ]
}
```

Region fields:

- `box`: `[left, top, right, bottom]` in original image pixels.
- `text`: final traditional Chinese text to draw.
- `font_size`, `min_font_size`, `bold`, `font`: typography controls.
- `fill`, `stroke_width`, `stroke_fill`: glyph color and optional outline.
- `background`: hex color, RGBA array, or `"sample"` to sample the region border.
- `padding`: number or `[left, top, right, bottom]`.
- `align`: `left`, `center`, or `right`.
- `valign`: `top`, `middle`, or `bottom`.
- `wrap`: default `true`.
- `fit`: use `"shrink"` to reduce font size until text fits.
- `strict_fit`: fail instead of silently overflowing.
- `radius`: optional rounded cover rectangle radius.
- `cover`: set `false` only when the background has already been cleaned.

## When to Write a Custom Script

Write a one-off rendering script instead of using the helper when the image contains multiple shape types, precise shadows, arrows, badges, or text integrated into non-rectangular components. In that script:

- Start from the original dimensions.
- Recreate only the components that must be redrawn.
- Use high-resolution rendering for text and shapes.
- Keep coordinates explicit and auditable.
- Inspect the final image with `view_image` or equivalent before responding.

## Final Response

Link the produced file. Briefly state that size/layout were preserved and summarize validation. If anything could not be verified, say exactly what remains uncertain.
