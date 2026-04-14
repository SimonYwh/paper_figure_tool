from dataclasses import dataclass


@dataclass
class CanvasSettings:
    width_mm: float = 210.0
    height_mm: float = 297.0
    dpi: int = 300

    @property
    def width_px(self) -> int:
        return int(round(self.width_mm / 25.4 * self.dpi))

    @property
    def height_px(self) -> int:
        return int(round(self.height_mm / 25.4 * self.dpi))