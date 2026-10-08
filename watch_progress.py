"""Show a live progress bar for an evaluation run.

  py watch_progress.py                          # watches results/esg_run_log.txt
  py watch_progress.py results/full_run_log.txt

Reads the run's log every few seconds; press Ctrl+C to stop watching (the run itself keeps going).
"""

import re
import sys
import time
from pathlib import Path

LOG = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "results" / "esg_run_log.txt"
WIDTH = 40


def main() -> None:
    started = time.time()
    while True:
        text = LOG.read_text(encoding="utf-8", errors="ignore") if LOG.exists() else ""
        designs = len(re.findall(r"^=== Design", text, flags=re.M))
        results = re.findall(r"^\s+(OK|PART|FAIL)\s+Q\s*(\d+)", text, flags=re.M)
        total = 38 if "esg" in LOG.name else 70
        done = len(results)
        finished = "=== Summary ===" in text

        if finished:
            stage = "Finished"
        elif designs == 0:
            stage = "Reading the PDFs (a few minutes)"
        else:
            stage = "Design A: read everything" if designs == 1 else "Design B: search first"
        filled = int(WIDTH * done / total)
        counts = {k: sum(1 for r in results if r[0] == k) for k in ("OK", "PART", "FAIL")}
        bar = "█" * filled + "░" * (WIDTH - filled)
        line = (f"\r[{bar}] {done}/{total} answers  "
                f"✓ {counts['OK']}  ~ {counts['PART']}  ✗ {counts['FAIL']}  | {stage} | watching {int(time.time() - started)}s   ")
        print(line, end="", flush=True)
        if finished:
            print("\n\n" + text[text.index("=== Summary ==="):])
            return
        time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped watching (the run continues in the background).")
