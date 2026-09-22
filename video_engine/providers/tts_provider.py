import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts

from video_engine.core.config import config
from video_engine.core.models import AudioTrack


class TTSProvider:
    def __init__(self, voice: str = None, rate: str = "+0%", volume: str = "+0%", pitch: str = "+0Hz"):
        self.voice = voice or config.TTS_VOICE
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    async def _generate_speech(self, text: str, output_path: Path):
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
            pitch=self.pitch,
        )
        await communicate.save(str(output_path))

    def generate(self, text: str, output_path: Path) -> AudioTrack:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            asyncio.run(self._generate_speech(text, output_path))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._generate_speech(text, output_path))
            loop.close()

        duration, sample_rate, channels = self._probe_audio(output_path)
        return AudioTrack(
            audio_path=str(output_path),
            duration=duration,
            sample_rate=sample_rate,
            channels=channels,
        )

    def _probe_audio(self, audio_path: Path):
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration:stream=sample_rate,channels",
            "-of", "json",
            str(audio_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            duration = float(data.get("format", {}).get("duration", 0.0))
            streams = data.get("streams", [{}])
            sample_rate = int(streams[0].get("sample_rate", 44100)) if streams else 44100
            channels = int(streams[0].get("channels", 2)) if streams else 2
            return duration, sample_rate, channels
        except Exception as exc:
            print(f"[TTSProvider] ffprobe error: {exc}")
            from moviepy import AudioFileClip

            clip = AudioFileClip(str(audio_path))
            duration = float(clip.duration or 0)
            clip.close()
            return duration, 44100, 2
