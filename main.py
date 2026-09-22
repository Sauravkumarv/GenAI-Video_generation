import argparse
import json
from pathlib import Path

from video_engine import generate_video


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a short-form AI video from a text prompt."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default=(
            "Create an ultra-realistic YouTube explainer about making AI videos "
            "look and sound real. Use photoreal documentary shots: a filmmaker "
            "operating a cinema camera, a rainy city street at dusk, and a close-up "
            "of real human skin and clothing texture. Calm tutorial narration."
        ),
        help="What the video should be about.",
    )
    parser.add_argument(
        "--aspect-ratio",
        default="16:9",
        choices=["9:16", "16:9", "1:1"],
        help="Output aspect ratio.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output/final_video.mp4",
        help="Output MP4 path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("[START] AI Video Agent")
    result = generate_video(
        prompt=args.prompt,
        aspect_ratio=args.aspect_ratio,
        output_path=str(output_path),
    )

    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
