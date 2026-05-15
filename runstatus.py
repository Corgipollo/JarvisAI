"""runstatus.py - wrapper sin underscores (ESP-LAA layout) para arrancar shared_status_writer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from jarvis_swarm.shared_status_writer import main
main()
