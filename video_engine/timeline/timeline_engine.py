from typing import List, Dict
from video_engine.core.models import SceneScriptPlan, AudioTrack, TimelineScene, CaptionWord


class AudioFirstTimelineEngine:
    """
    Calculates precise, non-overlapping scene timing dynamically from actual TTS audio measurements.
    """

    def calculate_timeline(
        self,
        script_plan: SceneScriptPlan,
        audio_tracks: Dict[int, AudioTrack],
        word_timestamps: Dict[int, List[CaptionWord]] = None
    ) -> List[TimelineScene]:
        word_timestamps = word_timestamps or {}
        timeline: List[TimelineScene] = []
        current_time = 0.0

        for scene_plan in script_plan.scenes:
            sn = scene_plan.scene_number
            audio_track = audio_tracks.get(sn)

            if audio_track and audio_track.duration > 0:
                # Use measured narration duration as authoritative scene duration
                scene_duration = round(audio_track.duration, 3)
            else:
                # Fallback to planned duration if audio generation failed
                scene_duration = float(scene_plan.planned_duration)

            start_time = round(current_time, 3)
            end_time = round(start_time + scene_duration, 3)
            current_time = end_time

            # Scene-specific word timestamps shifted to absolute timeline
            scene_words = word_timestamps.get(sn, [])
            abs_words: List[CaptionWord] = []
            for w in scene_words:
                abs_words.append(
                    CaptionWord(
                        word=w.word,
                        start=round(start_time + w.start, 3),
                        end=round(start_time + w.end, 3)
                    )
                )

            timeline_scene = TimelineScene(
                scene_number=sn,
                start_time=start_time,
                end_time=end_time,
                duration=scene_duration,
                narration_text=scene_plan.narration_text,
                visual_description=scene_plan.visual_description,
                caption=scene_plan.caption,
                motion=scene_plan.motion,
                transition=scene_plan.transition_in,
                audio_path=audio_track.audio_path if audio_track else None,
                words=abs_words
            )

            timeline.append(timeline_scene)

        return timeline
