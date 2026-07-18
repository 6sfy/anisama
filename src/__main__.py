import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    _script_dir = Path(__file__).resolve().parent
    if str(_script_dir.parent) not in sys.path:
        sys.path.insert(0, str(_script_dir.parent))
    __package__ = "src"

from .cli.app import main

if __name__ == "__main__":
    main()
