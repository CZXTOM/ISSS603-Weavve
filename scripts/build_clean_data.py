"""Run from the repository root; all generated data remains local."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from weavve.clean import main

if __name__ == "__main__":
    main()
