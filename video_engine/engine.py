from pathlib import Path
from typing import Optional, Dict, Any
from video_engine.pipeline.orchestrator import PipelineOrchestrator


def generate_video(
    prompt: str,
    aspect_ratio: str = "16:9",
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main developer-friendly entry point for the AI Video Generation Engine.
    """
    out_p = Path(output_path) if output_path else None
    orchestrator = PipelineOrchestrator()
    project = orchestrator.run_pipeline(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        output_path=out_p
    )

    qa = project.qa_report

    return {
        "status": "success" if (qa and qa.passed) else "failed",
        "video_path": project.rendered_video_path,
        "duration": project.spec.duration,
        "quality_score": qa.total_score if qa else 0.0,
        "scenes": len(project.timeline),
        "aspect_ratio": project.spec.aspect_ratio,
        "resolution": f"{project.spec.width}x{project.spec.height}",
        "qa": qa.model_dump() if qa else {}
    }
