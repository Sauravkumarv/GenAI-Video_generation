import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from video_engine.core.models import VideoSpec, ScenePlan, SceneScriptPlan, AudioTrack
from video_engine.timeline.timeline_engine import AudioFirstTimelineEngine
from video_engine.providers.visual_provider import VisualProvider
from video_engine.qa.qa_engine import QAEngine


def test_video_spec_and_schemas():
    spec = VideoSpec(width=1080, height=1920, fps=30, aspect_ratio="9:16")
    assert spec.width == 1080
    assert spec.height == 1920
    assert spec.fps == 30

    scene = ScenePlan(
        scene_number=1,
        planned_duration=5.0,
        narration_text="Test narration",
        visual_description="Cinematic sunset",
        caption="Sunset scene",
        motion="zoom_in",
    )
    assert scene.scene_number == 1
    assert scene.motion == "zoom_in"


def test_audio_first_timeline_engine():
    engine = AudioFirstTimelineEngine()
    script = SceneScriptPlan(
        title="Test Video",
        hook="Hook test",
        aspect_ratio="9:16",
        scenes=[
            ScenePlan(
                scene_number=1,
                planned_duration=5.0,
                narration_text="Short narration text.",
                visual_description="v1",
                caption="c1",
            ),
            ScenePlan(
                scene_number=2,
                planned_duration=5.0,
                narration_text="Longer narration text spoken here.",
                visual_description="v2",
                caption="c2",
            ),
        ],
    )
    tracks = {
        1: AudioTrack(audio_path="dummy1.mp3", duration=3.42),
        2: AudioTrack(audio_path="dummy2.mp3", duration=6.18),
    }

    timeline = engine.calculate_timeline(script, tracks)
    assert len(timeline) == 2
    assert timeline[0].start_time == 0.0
    assert timeline[0].end_time == 3.42
    assert timeline[0].duration == 3.42
    assert timeline[1].start_time == 3.42
    assert abs(timeline[1].end_time - 9.60) < 0.001
    assert timeline[1].duration == 6.18


def test_visual_asset_validation(tmp_path):
    provider = VisualProvider(width=1080, height=1920)
    fake_img = tmp_path / "test.png"

    assert not provider.validate_asset(tmp_path / "missing.png")

    fake_img.touch()
    assert not provider.validate_asset(fake_img)

    provider._generate_aesthetic_fallback("test visual", fake_img, 1)
    assert provider.validate_asset(fake_img)


def test_qa_engine_scoring():
    qa = QAEngine()
    report = qa.evaluate_project(None, Path("non_existent_video.mp4"))
    assert not report.passed
    assert report.total_score == 0.0


if __name__ == "__main__":
    import tempfile

    print("Running test_video_spec_and_schemas...")
    test_video_spec_and_schemas()
    print("Running test_audio_first_timeline_engine...")
    test_audio_first_timeline_engine()
    print("Running test_visual_asset_validation...")
    with tempfile.TemporaryDirectory() as tmp:
        test_visual_asset_validation(Path(tmp))
    print("Running test_qa_engine_scoring...")
    test_qa_engine_scoring()
    print("\n[OK] ALL ENGINE UNIT TESTS PASSED SUCCESSFULLY!")
