from pathlib import Path
from typing import Optional

from video_engine.core.models import QAReport, VideoProject
from video_engine.core.config import config


class QAEngine:
    """Scores a rendered video against measurable quality checks (100 points)."""

    def evaluate_project(self, project: Optional[VideoProject], video_path: Path) -> QAReport:
        problems = []
        category_scores = {}

        if not video_path.exists() or video_path.stat().st_size == 0:
            return QAReport(
                passed=False,
                total_score=0.0,
                category_scores={"render": 0.0},
                problems=["Rendered video file does not exist or is 0 bytes."],
            )

        if project is None:
            return QAReport(
                passed=False,
                total_score=0.0,
                category_scores={"render": 0.0},
                problems=["No project metadata available for QA."],
            )

        probe_data = self._probe_video(video_path)
        vol_data = self._probe_audio_volume(video_path)

        duration = float(probe_data.get("format", {}).get("duration", 0.0))
        video_stream = self._get_stream(probe_data, "video")
        audio_stream = self._get_stream(probe_data, "audio")

        width = int(video_stream.get("width", 0)) if video_stream else 0
        height = int(video_stream.get("height", 0)) if video_stream else 0
        codec = video_stream.get("codec_name", "") if video_stream else ""
        fps_eval = video_stream.get("r_frame_rate", "30/1") if video_stream else "30/1"
        try:
            num, den = map(int, fps_eval.split("/"))
            fps = num / den if den else 30.0
        except Exception:
            fps = 30.0

        has_audio = audio_stream is not None

        timeline_pts = 20.0
        expected_duration = sum(scene.duration for scene in project.timeline)
        duration_diff = abs(duration - expected_duration)
        if duration_diff > 0.5:
            timeline_pts -= 10.0
            problems.append(
                f"Duration mismatch: Actual {duration:.2f}s vs Expected {expected_duration:.2f}s"
            )
        elif duration_diff > 0.15:
            timeline_pts -= 3.0
            problems.append(f"Minor duration variance: {duration_diff:.2f}s")
        category_scores["timeline_sync"] = max(0.0, timeline_pts)

        audio_pts = 15.0
        if not has_audio:
            audio_pts = 0.0
            problems.append("Video has no audio track.")
        else:
            max_volume = vol_data.get("max_volume", -99.0)
            if max_volume > -0.1:
                audio_pts -= 4.0
                problems.append(f"Audio clipping detected (Max volume: {max_volume} dB)")
            mean_volume = vol_data.get("mean_volume", -99.0)
            if mean_volume < -45.0:
                audio_pts -= 5.0
                problems.append("Audio narration volume is excessively quiet.")
        category_scores["audio_quality"] = max(0.0, audio_pts)

        visual_pts = 20.0
        if width != project.spec.width or height != project.spec.height:
            visual_pts -= 10.0
            problems.append(
                f"Resolution mismatch: {width}x{height} vs expected {project.spec.width}x{project.spec.height}"
            )
        if codec not in ["h264", "hevc"]:
            visual_pts -= 5.0
            problems.append(f"Non-standard video codec: {codec}")
        category_scores["visual_integrity"] = max(0.0, visual_pts)

        caption_pts = 15.0
        missing_captions = [
            scene.scene_number
            for scene in project.timeline
            if not scene.caption and not scene.words
        ]
        if missing_captions:
            caption_pts -= 5.0 * len(missing_captions)
            problems.append(f"Missing caption data in scene(s): {missing_captions}")
        category_scores["caption_sync"] = max(0.0, caption_pts)

        render_pts = 10.0
        if abs(fps - project.spec.fps) > 1.0:
            render_pts -= 3.0
            problems.append(f"FPS variance: {fps:.1f} vs expected {project.spec.fps}")
        category_scores["rendering_integrity"] = max(0.0, render_pts)

        continuity_pts = 10.0
        if project.script_plan and len(project.timeline) != len(project.script_plan.scenes):
            continuity_pts -= 5.0
            problems.append("Rendered scene count differs from planned scene count.")
        category_scores["scene_continuity"] = max(0.0, continuity_pts)

        asset_pts = 10.0
        for scene in project.timeline:
            if not scene.asset_path or not Path(scene.asset_path).exists():
                asset_pts -= 3.0
                problems.append(f"Missing visual asset for scene {scene.scene_number}")
        category_scores["asset_validity"] = max(0.0, asset_pts)

        total_score = sum(category_scores.values())
        return QAReport(
            passed=total_score >= config.QA_PASS_THRESHOLD,
            total_score=total_score,
            category_scores=category_scores,
            problems=problems,
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            has_audio=has_audio,
            details={"volumedetect": vol_data},
        )

    def _probe_video(self, video_path: Path) -> dict:
        import json
        import subprocess

        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=codec_name,width,height,r_frame_rate,codec_type",
            "-of", "json",
            str(video_path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except Exception as exc:
            print(f"[QAEngine] ffprobe error: {exc}")
            return {}

    def _probe_audio_volume(self, video_path: Path) -> dict:
        import subprocess

        cmd = ["ffmpeg", "-i", str(video_path), "-af", "volumedetect", "-f", "null", "-"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            stderr = result.stderr or ""
            max_vol = -99.0
            mean_vol = -99.0
            for line in stderr.splitlines():
                if "max_volume:" in line:
                    max_vol = float(line.split("max_volume:")[1].split("dB")[0].strip())
                elif "mean_volume:" in line:
                    mean_vol = float(line.split("mean_volume:")[1].split("dB")[0].strip())
            return {"max_volume": max_vol, "mean_volume": mean_vol}
        except Exception:
            return {"max_volume": -99.0, "mean_volume": -99.0}

    def _get_stream(self, probe_data: dict, stream_type: str):
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == stream_type:
                return stream
        return None
