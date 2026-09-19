"""AQLEVON P4 runtime compatibility bootstrap.

Loaded by Python's site initialization when this directory is first on
PYTHONPATH. The actual compatibility logic lives in the versioned Worker03
module so the behavior is reviewable and testable.
"""
from p4_surrogate_tournament import install_runtime_compat

install_runtime_compat()
