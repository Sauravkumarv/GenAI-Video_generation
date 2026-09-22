import os
from typing import Optional

from dotenv import load_dotenv
from google import genai

from video_engine.core.config import config
from video_engine.core.models import SceneScriptPlan


load_dotenv()


ULTRA_REALISTIC_DIRECTOR = """
You are a director who makes AI footage look like real cameras, not AI art.
Follow the Tao Prompts approach: engineer the MEDIUM and STYLE first, then the scene.

Visual description rules (critical):
- Always name a real capture medium: ARRI Alexa 35, Sony FX3, Canon 5D Mark IV, iPhone 15 Pro, or 35mm Kodak Portra 400.
- Always name lens and light: 35mm/50mm, f/1.8-f/2.8, overcast daylight, tungsten practicals, golden hour, or fluorescent office.
- Describe real imperfections: skin pores, flyaway hair, fabric weave, dust, rain, slight motion blur, natural color cast.
- Forbidden: "8k", "cinematic wallpaper", "hyper-detailed CGI", "unreal engine", neon glow, illustration, anime, plastic skin.
- Each visual_description must be a single shot prompt a still-image model can render.

Narration:
- Calm, documentary, tutorial tone. Sound like a YouTube filmmaker explaining craft.
- 12-22 words per scene. No hype slogans.

Captions: 3-6 words, lowercase-friendly, editorial.
Motion: prefer slow zoom_in or static so the shot feels like handheld documentary, not a slideshow.
"""


class LLMProvider:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing from environment variables.")
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name or config.GEMINI_MODEL

    def generate_script_plan(self, prompt: str, aspect_ratio: str = "16:9", target_scenes: int = 3) -> SceneScriptPlan:
        system_instruction = f"""
{ULTRA_REALISTIC_DIRECTOR}

Target specs:
- Aspect ratio: {aspect_ratio}
- Scene count: {target_scenes}
- Total duration: about 15 to 22 seconds.

Also provide:
1. hook: one opening line for scene 1
2. music_prompt: quiet documentary underscore, no EDM
"""
        full_prompt = f"{system_instruction}\n\nUser Request: {prompt}"
        last_error = None
        models = [self.model_name, *config.GEMINI_FALLBACK_MODELS]
        seen = []
        for model in models:
            if model in seen:
                continue
            seen.append(model)
            try:
                print(f"[LLMProvider] Using model: {model}")
                response = self.client.models.generate_content(
                    model=model,
                    contents=full_prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": SceneScriptPlan,
                    },
                )
                script_plan = SceneScriptPlan.model_validate_json(response.text)
                script_plan.aspect_ratio = aspect_ratio
                return script_plan
            except Exception as exc:
                last_error = exc
                print(f"[LLMProvider] {model} failed: {exc}")

        raise RuntimeError(f"Gemini script generation failed: {last_error}")
