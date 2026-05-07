import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from automation.run_pipeline import _build_run_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a Family Rule Testing artifact.")
    parser.add_argument("artifact", help="Path to a JSON artifact created by automation/run_pipeline.py")
    args = parser.parse_args()

    artifact = json.loads(Path(args.artifact).read_text())
    summary = artifact.get("summary") or _build_run_summary(artifact, artifact.get("mode", "review-summary"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
