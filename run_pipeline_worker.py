"""
run_pipeline_worker.py — Subprocess entry point for the pipeline.

Streamlit runs this as a child process to avoid blocking/killing the main UI.
Writes the serialized result to a JSON file when done.

Usage:
    python run_pipeline_worker.py "<task>" /tmp/result.json
"""

import sys
import json
from pathlib import Path
from pipeline import run_pipeline

if __name__ == "__main__":
    task       = sys.argv[1]
    out_path   = sys.argv[2]

    result = run_pipeline(task)

    serializable = {
        "status":               result["status"],
        "task":                 result["task"],
        "plan":                 result["plan"],
        "generated_files":      result["generated_files"],
        "outputs":              result["outputs"],
        "errors":               result["errors"],
        "assembled_app":        result.get("assembled_app", ""),
        "assembled_app_path":   result.get("assembled_app_path", ""),
        "logs":                 result["logs"],
        "test_result":          result.get("test_result", {}),
    }

    Path(out_path).write_text(json.dumps(serializable, default=str), encoding="utf-8")
