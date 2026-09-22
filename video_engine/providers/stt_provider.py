from pathlib import Path
from typing import List

from video_engine.core.config import config
from video_engine.core.models import CaptionWord


class STTProvider:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or config.WHISPER_MODEL
        self._model = None

    @property
    def model(self):
        if self._model is None:
            import whisper

            print(f"[STTProvider] Loading Whisper model '{self.model_name}'...")
            self._model = whisper.load_model(self.model_name)
        return self._model

    def transcribe(self, audio_path: Path) -> List[CaptionWord]:
        result = self.model.transcribe(str(audio_path), word_timestamps=True)
        words: List[CaptionWord] = []
        for segment in result.get("segments", []):
            for word_info in segment.get("words", []):
                word_text = str(word_info.get("word", "")).strip()
                if not word_text:
                    continue
                words.append(
                    CaptionWord(
                        word=word_text,
                        start=float(word_info.get("start", 0.0)),
                        end=float(word_info.get("end", 0.0)),
                    )
                )
        return words
