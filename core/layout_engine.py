from __future__ import annotations


def apply_grid_layout(items, page_w: int, page_h: int, rows: int, cols: int, margin: int = 40, gap: int = 20):
    """把 items 按 rows x cols 排版到页面中。"""
    rows = max(1, int(rows))
    cols = max(1, int(cols))
    margin = max(0, int(margin))
    gap = max(0, int(gap))

    usable_w = page_w - margin * 2 - gap * (cols - 1)
    usable_h = page_h - margin * 2 - gap * (rows - 1)
    if usable_w <= 10 or usable_h <= 10:
        raise ValueError("页面太小或边距/间距过大，无法排版。")

    cell_w = usable_w / cols
    cell_h = usable_h / rows

    for idx, item in enumerate(items):
        r = idx // cols
        c = idx % cols
        if r >= rows:
            break
        x = margin + c * (cell_w + gap)
        y = margin + r * (cell_h + gap)
        item.set_frame_size(cell_w, cell_h)
        item.setPos(x, y)