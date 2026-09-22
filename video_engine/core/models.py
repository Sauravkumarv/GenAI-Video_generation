from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class VideoSpec(BaseModel):
    width: int = Field(default=1080, description="Video width in pixels")
    height: int = Field(default=1920, description="Video height in pixels")
    fps: int = Field(default=30, description="Frames per second")
    duration: float = Field(default=0.0, description="Total video duration in seconds")
    aspect_ratio: str = Field(default="9:16", description="Aspect ratio e.g. 9:16, 16:9, 1:1")


class CaptionWord(BaseModel):
    word: str
    start: float
    end: float


class CaptionSegment(BaseModel):
    start: float
    end: float
    text: str
    words: List[CaptionWord] = Field(default_factory=list)


class ScenePlan(BaseModel):
    scene_number: int = Field(description="1-indexed scene number")
    planned_duration: float = Field(description="Target estimated duration in seconds")
    narration_text: str = Field(description="Spoken text for narration")
    visual_description: str = Field(description="Detailed image/video prompt description")
    caption: str = Field(description="Short text for caption overlay")
    motion: str = Field(default="zoom_in", description="Camera motion: zoom_in, zoom_out, pan_left, pan_right, static")
    transition_in: str = Field(default="fade", description="Transition in: fade, cut, none")
    transition_out: str = Field(default="fade", description="Transition out: fade, cut, none")


class SceneScriptPlan(BaseModel):
    title: str = Field(description="Title of the video script")
    hook: str = Field(description="Opening hook statement")
    aspect_ratio: str = Field(default="9:16", description="Target aspect ratio")
    scenes: List[ScenePlan] = Field(description="List of scenes")
    music_prompt: str = Field(default="inspirational ambient cinematic background music", description="Background music theme")


class AudioTrack(BaseModel):
    audio_path: str
    duration: float
    sample_rate: int = 44100
    channels: int = 2
    words: List[CaptionWord] = Field(default_factory=list)


class TimelineScene(BaseModel):
    scene_number: int
    start_time: float
    end_time: float
    duration: float
    narration_text: str
    visual_description: str
    caption: str
    motion: str
    transition: str
    audio_path: Optional[str] = None
    asset_path: Optional[str] = None
    asset_type: str = "image"  # image or video
    words: List[CaptionWord] = Field(default_factory=list)


class QAReport(BaseModel):
    passed: bool
    total_score: float = Field(description="Total QA score out of 100")
    category_scores: Dict[str, float] = Field(default_factory=dict)
    problems: List[str] = Field(default_factory=list)
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class VideoProject(BaseModel):
    project_id: str
    prompt: str
    spec: VideoSpec
    script_plan: SceneScriptPlan
    timeline: List[TimelineScene] = Field(default_factory=list)
    narration_audio_paths: Dict[int, str] = Field(default_factory=dict)
    music_path: Optional[str] = None
    rendered_video_path: Optional[str] = None
    qa_report: Optional[QAReport] = None
    retry_count: int = 0
