"""Ray worker bootstrap for AQLEVON P4 runtime compatibility.

Ray applies worker_process_setup_hook after the worker process starts but
before Tasks and Actors are scheduled. That timing is required for the pinned
Transformers 5.17 / SDPO compatibility alias because setting PYTHONPATH in a
runtime_env happens too late for Python startup-time sitecustomize import.
"""


def install() -> None:
    from p4_surrogate_tournament import install_runtime_compat
    install_runtime_compat()
