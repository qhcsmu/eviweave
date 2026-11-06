"""Compatibility command; implementation is in artifacts/tools/."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[1]/'artifacts/tools/fetch_v03_artifacts.py'), run_name='__main__')
