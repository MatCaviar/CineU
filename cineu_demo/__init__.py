"""CineU research-system demo implementation.

This package is intentionally local-first: JSON/JSONL/YAML files are the
canonical source of truth, while Unreal integration is exposed through a runner
interface. The default MockRunner allows the whole orchestration chain to be
validated without a local Unreal installation.
"""

__version__ = "0.3.1"
