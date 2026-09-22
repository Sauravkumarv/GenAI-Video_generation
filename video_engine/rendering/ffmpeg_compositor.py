import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from video_engine.core.models import TimelineScene, VideoProject, VideoSpec
from video_engine.core.config import config


class FFmpegCompositor:
    """Renders scenes with Ken Burns motion, mixed narration, and burned-in captions."""

    def __init__(self, spec: VideoSpec):
        self.spec = spec
        self.width = spec.width
        self.height = spec.height
        self.fps = spec.fps
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg is not on PATH. Install FFmpeg before rendering.")

    def render_project(
        self,
        project: VideoProject,
        output_path: Path,
        background_music_path: Optional[Path] = None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = config.TEMP_DIR / project.project_id
        temp_dir.mkdir(parents=True, exist_ok=True)

        print(f"[FFmpegCompositor] Starting render for project {project.project_id}...")

        scene_video_paths: List[Path] = []
        for scene in project.timeline:
            scene_mp4 = temp_dir / f"scene_{scene.scene_number}.mp4"
            self._render_scene_clip(scene, scene_mp4)
            scene_video_paths.append(scene_mp4)

        concatenated_video = temp_dir / "concatenated_visual.mp4"
        self._concat_scenes(scene_video_paths, concatenated_video)

        master_audio = temp_dir / "master_audio.m4a"
        self._mix_audio_tracks(project.timeline, master_audio, background_music_path)

        subtitles_file = temp_dir / "captions.ass"
        has_captions = self._generate_ass_subtitles(project.timeline, subtitles_file)

        self._assemble_final_mp4(
            video_path=concatenated_video,
            audio_path=master_audio,
            subtitles_path=subtitles_file if has_captions else None,
            output_path=output_path,
        )

        print(f"[FFmpegCompositor] Final MP4 successfully rendered: {output_path}")
        return output_path

    def _render_scene_clip(self, scene: TimelineScene, output_path: Path):
        if not scene.asset_path or not Path(scene.asset_path).exists():
            raise FileNotFoundError(f"Missing visual asset for scene {scene.scene_number}")

        duration = max(float(scene.duration), 0.5)
        frames = max(int(round(duration * self.fps)), 1)
        zoom = self._zoompan_filter(scene.motion, frames)

        vf = (
            f"scale={self.width * 2}:{self.height * 2}:force_original_aspect_ratio=increase,"
            f"crop={self.width * 2}:{self.height * 2},"
            f"{zoom},"
            "format=yuv420p"
        )

        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-framerate", str(self.fps),
            "-loop", "1",
            "-i", str(scene.asset_path),
            "-t", f"{duration:.3f}",
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            str(output_path),
        ]
        subprocess.run(cmd, check=True)

    def _zoompan_filter(self, motion: str, frames: int) -> str:
        size = f"s={self.width}x{self.height}:fps={self.fps}"
        if motion == "zoom_out":
            return (
                f"zoompan=z='if(eq(on,1),1.15,max(1.0,zoom-0.0015))'"
                f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:{size}"
            )
        if motion == "pan_left":
            return (
                f"zoompan=z='1.1':x='if(eq(on,1),iw*0.08,max(0,x-1))'"
                f":y='ih/2-(ih/zoom/2)':d={frames}:{size}"
            )
        if motion == "pan_right":
            return (
                f"zoompan=z='1.1':x='if(eq(on,1),0,min(iw*0.08,x+1))'"
                f":y='ih/2-(ih/zoom/2)':d={frames}:{size}"
            )
        if motion == "static":
            return (
                f"zoompan=z='1':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:{size}"
            )
        return (
            f"zoompan=z='min(zoom+0.0015,1.15)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:{size}"
        )

    def _concat_scenes(self, scene_paths: List[Path], output_path: Path):
        concat_txt = output_path.parent / "concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as handle:
            for path in scene_paths:
                handle.write(f"file '{path.resolve().as_posix()}'\n")

        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(concat_txt),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-r", str(self.fps),
            str(output_path),
        ]
        subprocess.run(cmd, check=True)

    def _mix_audio_tracks(
        self,
        timeline: List[TimelineScene],
        output_path: Path,
        bg_music_path: Optional[Path] = None,
    ):
        temp_dir = output_path.parent
        padded_clips: List[Path] = []

        for scene in timeline:
            padded = temp_dir / f"narration_{scene.scene_number}.m4a"
            duration = max(float(scene.duration), 0.5)
            if scene.audio_path and Path(scene.audio_path).exists():
                cmd = [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(scene.audio_path),
                    "-af", f"apad,atrim=0:{duration:.3f},asetpts=PTS-STARTPTS",
                    "-c:a", "aac", "-b:a", "192k",
                    str(padded),
                ]
            else:
                cmd = [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-f", "lavfi",
                    "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", f"{duration:.3f}",
                    "-c:a", "aac", "-b:a", "192k",
                    str(padded),
                ]
            subprocess.run(cmd, check=True)
            padded_clips.append(padded)

        concat_txt = temp_dir / "audio_concat_list.txt"
        with open(concat_txt, "w", encoding="utf-8") as handle:
            for path in padded_clips:
                handle.write(f"file '{path.resolve().as_posix()}'\n")

        narration_combined = temp_dir / "narration_combined.m4a"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                "-c:a", "aac", "-b:a", "192k",
                str(narration_combined),
            ],
            check=True,
        )

        if bg_music_path and bg_music_path.exists():
            subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(narration_combined),
                    "-stream_loop", "-1", "-i", str(bg_music_path),
                    "-filter_complex",
                    "[1:a]volume=0.12[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
                    "-map", "[a]",
                    "-c:a", "aac", "-b:a", "192k",
                    str(output_path),
                ],
                check=True,
            )
            return

        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(narration_combined),
                "-c:a", "aac", "-b:a", "192k",
                str(output_path),
            ],
            check=True,
        )

    def _generate_ass_subtitles(self, timeline: List[TimelineScene], output_path: Path) -> bool:
        margin_v = 140 if self.height >= 1920 else 80
        font_size = 54 if self.height >= 1920 else 36
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.width}
PlayResY: {self.height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H00000000,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,3,2,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        lines = [header]
        has_dialogue = False

        for scene in timeline:
            if scene.words:
                group_size = 4
                words = scene.words
                for index in range(0, len(words), group_size):
                    chunk = words[index:index + group_size]
                    if not chunk:
                        continue
                    text = " ".join(word.word for word in chunk).replace("\\", "\\\\").replace("{", "\\{")
                    lines.append(
                        f"Dialogue: 0,{self._format_ass_time(chunk[0].start)},"
                        f"{self._format_ass_time(chunk[-1].end)},Default,,0,0,0,,{text}\n"
                    )
                    has_dialogue = True
            elif scene.caption:
                text = scene.caption.replace("\\", "\\\\").replace("{", "\\{")
                lines.append(
                    f"Dialogue: 0,{self._format_ass_time(scene.start_time)},"
                    f"{self._format_ass_time(scene.end_time)},Default,,0,0,0,,{text}\n"
                )
                has_dialogue = True

        if not has_dialogue:
            return False

        with open(output_path, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
        return True

    def _format_ass_time(self, seconds: float) -> str:
        total_cs = int(round(max(seconds, 0.0) * 100))
        h, rem = divmod(total_cs, 360000)
        m, rem = divmod(rem, 6000)
        s, cs = divmod(rem, 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _assemble_final_mp4(
        self,
        video_path: Path,
        audio_path: Path,
        subtitles_path: Optional[Path],
        output_path: Path,
    ):
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(video_path),
            "-i", str(audio_path),
        ]
        if subtitles_path and subtitles_path.exists():
            escaped = str(subtitles_path.resolve()).replace("\\", "/").replace(":", "\\:")
            cmd.extend(["-vf", f"subtitles='{escaped}'"])
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18"])
        else:
            cmd.extend(["-c:v", "copy"])

        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest", str(output_path)])
        subprocess.run(cmd, check=True)
