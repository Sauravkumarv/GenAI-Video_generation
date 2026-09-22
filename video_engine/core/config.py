import os
from pathlib import Path
from pydantic import BaseModel


class Config(BaseModel):
    # Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    ASSETS_DIR: Path = BASE_DIR / "assets"
    AUDIO_DIR: Path = ASSETS_DIR / "audio"
    IMAGES_DIR: Path = ASSETS_DIR / "images"
    VIDEOS_DIR: Path = ASSETS_DIR / "videos"
    TEMP_DIR: Path = BASE_DIR / "temp"
    OUTPUT_DIR: Path = BASE_DIR / "output"

    # Default Render Specs
    DEFAULT_FPS: int = 30
    DEFAULT_ASPECT_RATIO: str = "16:9"
    
    ASPECT_RATIOS: dict = {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
    }

    # QA & Self-Correction
    QA_PASS_THRESHOLD: float = 95.0
    MAX_RETRIES: int = 3

    # Providers
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_FALLBACK_MODELS: list = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-flash-latest",
    ]
    TTS_VOICE: str = "en-US-AndrewNeural"
    WHISPER_MODEL: str = "tiny"
    IMAGE_MODEL: str = "flux"


config = Config()

# Ensure directories exist
for path in [
    config.ASSETS_DIR,
    config.AUDIO_DIR,
    config.IMAGES_DIR,
    config.VIDEOS_DIR,
    config.TEMP_DIR,
    config.OUTPUT_DIR
]:
    path.mkdir(parents=True, exist_ok=True)
