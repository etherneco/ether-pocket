"""Fixed root-owned import directory; isolated Python ignores caller PYTHONPATH."""
import sys
sys.path.insert(0, '/usr/share/etherhardware')
from repair import main
main()
