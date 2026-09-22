import json
import uuid
from pathlib import Path
from typing import Optional, Dict

from video_engine.core.models import VideoProject, VideoSpec, AudioTrack, QAReport
from video_engine.core.config import config
from video_engine.providers.llm_provider import LLMProvider
from video_engine.providers.tts_provider import TTSProvider
from video_engine.providers.visual_provider import VisualProvider
from video_engine.providers.stt_provider import STTProvider
from video_engine.timeline.timeline_engine import AudioFirstTimelineEngine
from video_engine.rendering.ffmpeg_compositor import FFmpegCompositor
from video_engine.qa.qa_engine import QAEngine


class PipelineOrchestrator:
    """
    End-to-End AI Video Generation Pipeline Orchestrator with Self-Correction Loop.
    """

    def __init__(self):
        self.llm = LLMProvider()
        self.tts = TTSProvider()
        self.stt = STTProvider()
        self.timeline_engine = AudioFirstTimelineEngine()
        self.qa_engine = QAEngine()

    def run_pipeline(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        output_path: Optional[Path] = None
    ) -> VideoProject:
        project_id = str(uuid.uuid4())[:8]
        width, height = config.ASPECT_RATIOS.get(aspect_ratio, (1080, 1920))
        spec = VideoSpec(width=width, height=height, fps=config.DEFAULT_FPS, aspect_ratio=aspect_ratio)

        print("=" * 60)
        print(f"[PIPELINE] Starting Video Generation Engine - Project ID: {project_id}")
        print(f"[PIPELINE] Prompt: '{prompt}'")
        print(f"[PIPELINE] Aspect Ratio: {aspect_ratio} ({width}x{height})")
        print("=" * 60)

        # Step 1: Script & Scene Planning
        print("\n[PLANNER] Generating Script and Scene Breakdown via Gemini...")
        script_plan = self.llm.generate_script_plan(prompt, aspect_ratio=aspect_ratio)
        print(f"[PLANNER] Title: {script_plan.title}")
        print(f"[PLANNER] Generated {len(script_plan.scenes)} scenes.")

        project = VideoProject(
            project_id=project_id,
            prompt=prompt,
            spec=spec,
            script_plan=script_plan
        )

        # Instantiate VisualProvider with spec resolution
        visual_provider = VisualProvider(width=width, height=height)

        # Step 2: TTS Generation & Audio Measurement
        print("\n[TTS] Generating Narration Audio and measuring durations...")
        audio_tracks: Dict[int, AudioTrack] = {}
        scene_word_timestamps = {}

        for scene in script_plan.scenes:
            sn = scene.scene_number
            audio_file = config.AUDIO_DIR / f"{project_id}_scene_{sn}.mp3"
            print(f"[TTS] Scene {sn}: '{scene.narration_text[:40]}...'")
            audio_track = self.tts.generate(scene.narration_text, audio_file)
            audio_tracks[sn] = audio_track
            project.narration_audio_paths[sn] = str(audio_file)
            print(f"[TTS] Scene {sn} audio duration = {audio_track.duration:.2f}s")

            # Extract word-level timestamps using Whisper
            try:
                words = self.stt.transcribe(audio_file)
                scene_word_timestamps[sn] = words
            except Exception as e:
                print(f"[STT] Warning: Word timestamp transcription failed for scene {sn}: {e}")
                scene_word_timestamps[sn] = []

        # Step 3: Audio-First Timeline Calculation
        print("\n[TIMELINE] Recalculating scene boundaries from measured TTS durations...")
        timeline = self.timeline_engine.calculate_timeline(script_plan, audio_tracks, scene_word_timestamps)
        total_duration = sum(s.duration for s in timeline)
        project.spec.duration = round(total_duration, 2)
        project.timeline = timeline

        print(f"[TIMELINE] Total video duration calculated: {total_duration:.2f}s across {len(timeline)} scenes.")
        for s in timeline:
            print(f"   Scene {s.scene_number}: {s.start_time:.2f}s -> {s.end_time:.2f}s (duration: {s.duration:.2f}s)")

        # Step 4: Visual Asset Generation & Validation
        print("\n[ASSETS] Generating and validating visual assets...")
        for scene in project.timeline:
            asset_file = config.IMAGES_DIR / f"{project_id}_scene_{scene.scene_number}.png"
            asset_path = visual_provider.generate_asset(
                scene.visual_description,
                asset_file,
                scene_number=scene.scene_number
            )
            scene.asset_path = asset_path

        # Step 5: Render & QA Self-Correction Loop
        output_file = output_path or (config.OUTPUT_DIR / f"video_{project_id}.mp4")
        compositor = FFmpegCompositor(project.spec)

        for attempt in range(1, config.MAX_RETRIES + 1):
            print(f"\n[RENDER] Render Attempt {attempt}/{config.MAX_RETRIES}...")
            compositor.render_project(project, output_file)
            project.rendered_video_path = str(output_file)

            print(f"\n[QA] Running Automated 100-Point Quality Analysis...")
            qa_report = self.qa_engine.evaluate_project(project, output_file)
            project.qa_report = qa_report

            print(f"[QA] Score = {qa_report.total_score:.1f}/100 | Passed = {qa_report.passed}")
            for cat, pts in qa_report.category_scores.items():
                print(f"   - {cat}: {pts:.1f} pts")

            if qa_report.passed:
                print(f"\n[PIPELINE SUCCESS] Video generated meeting QA threshold (>= {config.QA_PASS_THRESHOLD})!")
                break
            else:
                print(f"\n[QA DEFECTS DETECTED]:")
                for prob in qa_report.problems:
                    print(f"   - {prob}")

                if attempt < config.MAX_RETRIES:
                    print(f"\n[SELF-CORRECTION] Attempting fix for re-render {attempt + 1}...")
                    project.retry_count = attempt
                    self._apply_self_correction(project, qa_report, visual_provider)

        # Save project manifest project.json
        manifest_path = output_file.parent / f"{output_file.stem}_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(project.model_dump_json(indent=2))

        print(f"\n[MANIFEST] Saved project manifest: {manifest_path}")
        return project

    def _apply_self_correction(self, project: VideoProject, qa: QAReport, visual_provider: VisualProvider):
        """Regenerate missing assets and keep timeline durations aligned with audio."""
        for scene in project.timeline:
            asset_missing = not scene.asset_path or not Path(scene.asset_path).exists()
            if asset_missing or any("Missing visual asset" in problem for problem in qa.problems):
                if asset_missing:
                    asset_file = config.IMAGES_DIR / f"{project.project_id}_scene_{scene.scene_number}_retry.png"
                    scene.asset_path = visual_provider.generate_asset(
                        scene.visual_description,
                        asset_file,
                        scene.scene_number,
                    )
