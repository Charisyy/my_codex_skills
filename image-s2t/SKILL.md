---
name: image-s2t
description: Convert simplified Chinese text inside images to traditional Chinese while preserving all other visual elements. Use when the user asks to translate image text from 简体中文/简体字 to 繁体中文/繁体字, especially for screenshots, flowcharts, posters, diagrams, UI captures, GIF/video frames, or any request that says layout, elements, colors, size, clarity, or “其他不要改变” must be preserved.
---

# Image S2T

## Purpose

Convert only the simplified Chinese text in an image to traditional Chinese. Preserve the canvas size, layout, colors, icons, lines, arrows, backgrounds, shadows, spacing, and all non-text elements unless the user explicitly requests a change.

## Core Rules

- Do not use generative image editing for text replacement when deterministic redrawing can work. Text must be crisp and legible.
- Do not paraphrase, embellish, summarize, or “improve” the wording. Convert simplified Chinese to traditional Chinese only.
- Preserve numbers, Latin letters, punctuation intent, units, formulas, symbols, and spacing unless a script conversion requires the Chinese punctuation variant.
- Keep the original image dimensions unless the user asks for another size.
- Save the result as a new file. Do not overwrite the source unless the user explicitly asks.
- Before delivery, visually inspect the output and verify there are no missing elements, mojibake, question marks, clipped text, blurred text, or text overflow.

## Workflow

1. Inspect the source image.
   - Record dimensions, file type, and obvious text regions.
   - If exact coordinates matter, use scripts, screenshots, or local image inspection to identify bounding boxes.

2. Transcribe the simplified text exactly.
   - Prefer manual transcription for short diagrams and screenshots.
   - Use OCR only as a starting point; correct OCR errors against the image.

3. Convert text to traditional Chinese.
   - Prefer OpenCC with `s2t` or `s2tw` when available.
   - If OpenCC is unavailable, convert carefully by knowledge and verify every phrase.
   - Do not convert product names, code identifiers, English, formulas, or numeric values.

4. Rebuild only the text areas.
   - For simple flat backgrounds, cover the old text with the local background color and redraw.
   - For boxes/cards with uniform fill, redraw the box or cover the old text inside the box and redraw text.
   - For complex backgrounds, preserve the image and use a localized inpaint/clone approach only for the text background, then redraw text.
   - Match original font weight, size, color, alignment, and line spacing as closely as possible. Use a CJK-capable font such as Microsoft YaHei, SimHei, Noto Sans CJK, Source Han Sans, PingFang, or equivalent.

5. Validate.
   - Open the output image and inspect at normal and zoomed sizes.
   - Confirm every simplified phrase has become traditional.
   - Confirm all non-text elements are intact.
   - Confirm text is sharp, not anti-aliased into mush, not clipped, and not outside its original visual container.
   - For animated GIFs, validate frame count, timing, dimensions, and representative frames. If text appears across many frames, process frames consistently and reassemble without changing timing.

## Helper Script

Use `scripts/overlay_text_regions.py` when the job can be expressed as rectangular text replacements. It takes a JSON spec and writes a raster image with text redrawn over the original.

Example spec:

```json
{
  "source": "C:/path/input.png",
  "output": "C:/path/output.png",
  "default_font": "C:/Windows/Fonts/msyh.ttc",
  "default_bold_font": "C:/Windows/Fonts/msyhbd.ttc",
  "scale": 3,
  "regions": [
    {
      "box": [52, 28, 360, 64],
      "text": "辦公用品數據篩選與計算流程",
      "font_size": 25,
      "bold": true,
      "fill": "#0e1c34",
      "background": "#f6f8fb",
      "align": "left",
      "valign": "middle"
    }
  ]
}
```

Run:

```bash
python scripts/overlay_text_regions.py spec.json
```

If the original layout contains shapes, arrows, shadows, or text embedded inside rounded boxes, it is often better to write a small custom rendering script for that image, using the original dimensions and coordinates. Keep the same validation standard.

## Output

In the final response, link the produced file and briefly state what was preserved and how it was checked. Mention any limitations only if validation could not be completed.
