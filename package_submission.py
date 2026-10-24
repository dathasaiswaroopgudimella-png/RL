"""OpsArena Packaging Script for Confluentia Hackathon (Team team_087).

Packages a clean, compliant submission archive:
- EXCLUDES: .env, .git/, __pycache__/, .pytest_cache/, temporary scripts.
- INCLUDES: code, docker files, README, 2-page design-doc.pdf, 10-slide deck.pdf,
  baseline-results/gate.json, 3 real model run folders in test-run-logs/,
  and 2 sample trajectories with SRE post-mortems.
"""
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ZIP_PATH = ROOT / "team_087.zip"

INCLUDED_PATTERNS = [
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "docker-compose.yml",
    "Dockerfile.harness",
    "Dockerfile.sandbox",
    "requirements.txt",
    "LICENSE",
    "README.md",
    "design-doc.pdf",
    "deck.pdf",
    "baseline-results/gate.json",
    "baseline-results/gate.jsonl",
    "inputs/.gitkeep",
    "inputs/README.md",
    "logs/.gitkeep",
]

INCLUDED_DIRS = [
    "harness",
    "sandbox",
    "sample-trajectories",
    "test-run-logs",
    "tests",
]


def should_include_file(rel_path: str) -> bool:
    # Strict security & cleanliness filters
    if ".env" in rel_path and not rel_path.endswith(".env.example"):
        return False
    if "__pycache__" in rel_path or rel_path.endswith(".pyc"):
        return False
    if ".pytest_cache" in rel_path or ".git" in rel_path:
        return False
    if rel_path in ("check_model.py", "build_submission_docs.py", "package_submission.py"):
        return False
    return True


def package():
    if ZIP_PATH.is_file():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Add root files
        for item in INCLUDED_PATTERNS:
            p = ROOT / item
            if p.is_file():
                zf.write(p, arcname=item)
                print(f"Added: {item}")

        # Add directories
        for d in INCLUDED_DIRS:
            d_path = ROOT / d
            for root, dirs, files in os.walk(d_path):
                for f in files:
                    full_p = Path(root) / f
                    rel_p = str(full_p.relative_to(ROOT)).replace("\\", "/")
                    if should_include_file(rel_p):
                        zf.write(full_p, arcname=rel_p)
                        print(f"Added: {rel_p}")

    print(f"\nSuccessfully created {ZIP_PATH.name} ({ZIP_PATH.stat().st_size:,} bytes)")


if __name__ == "__main__":
    package()
