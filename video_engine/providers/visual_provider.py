import random
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from video_engine.core.config import config


class VisualProvider:
    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height

    def generate_asset(self, visual_description: str, output_path: Path, scene_number: int = 1) -> str:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if self._fetch_pollinations(visual_description, output_path) and self.validate_asset(output_path):
            self._fit_canvas(output_path)
            print(f"[VisualProvider] Generated photoreal asset: {output_path.name}")
            return str(output_path)

        print(f"[VisualProvider] Using fallback aesthetic renderer for scene {scene_number}")
        self._generate_aesthetic_fallback(visual_description, output_path, scene_number)

        if self.validate_asset(output_path):
            return str(output_path)

        raise RuntimeError(f"Failed to generate valid visual asset for scene {scene_number}")

    def _build_prompt(self, prompt: str) -> str:
        return (
            "photoreal still from a real camera, not AI art, not illustration, "
            "natural color, visible film grain, authentic lighting, "
            f"{prompt}, "
            "shot on ARRI Alexa 35 with a 50mm lens, f/2.0, "
            "real skin texture, real fabric, slight imperfections, documentary photography"
        )

    def _fetch_pollinations(self, prompt: str, output_path: Path) -> bool:
        enhanced_prompt = self._build_prompt(prompt)
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        seed = random.randint(1000, 999999)
        model = getattr(config, "IMAGE_MODEL", "flux")
        url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width={self.width}&height={self.height}&nologo=true&enhance=true"
            f"&model={model}&seed={seed}"
        )
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                if response.status == 200:
                    data = response.read()
                    if len(data) > 8000:
                        output_path.write_bytes(data)
                        return True
        except Exception as exc:
            print(f"[VisualProvider] Image generation download failed: {exc}")
        return False

    def _fit_canvas(self, output_path: Path):
        with Image.open(output_path) as image:
            fitted = ImageOps.fit(
                image.convert("RGB"),
                (self.width, self.height),
                method=Image.Resampling.LANCZOS,
            )
            fitted.save(output_path, "PNG")

    def _generate_aesthetic_fallback(self, prompt: str, output_path: Path, scene_number: int):
        img = Image.new("RGB", (self.width, self.height), color=(15, 17, 23))
        draw = ImageDraw.Draw(img)
        palettes = [
            [(28, 24, 20), (92, 78, 62)],
            [(18, 22, 28), (48, 62, 74)],
            [(22, 18, 16), (70, 52, 40)],
        ]
        start, end = palettes[(scene_number - 1) % len(palettes)]

        for y in range(self.height):
            ratio = y / max(self.height - 1, 1)
            color = (
                int(start[0] + (end[0] - start[0]) * ratio),
                int(start[1] + (end[1] - start[1]) * ratio),
                int(start[2] + (end[2] - start[2]) * ratio),
            )
            draw.line([(0, y), (self.width, y)], fill=color)

        glow = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        cx, cy = self.width // 2, self.height // 3
        glow_draw.ellipse([cx - 280, cy - 180, cx + 280, cy + 180], fill=(255, 240, 210, 28))
        glow = glow.filter(ImageFilter.GaussianBlur(70))
        img.paste(glow, (0, 0), glow)
        img.save(output_path, "PNG")

    def validate_asset(self, file_path: Path) -> bool:
        if not file_path.exists() or file_path.stat().st_size == 0:
            return False
        try:
            with Image.open(file_path) as img:
                img.verify()
            return True
        except Exception as exc:
            print(f"[Validation Error] Image file unreadable ({file_path}): {exc}")
            return False
