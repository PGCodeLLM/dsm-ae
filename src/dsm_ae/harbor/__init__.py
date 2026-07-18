"""Harbor migration bridge for DSM-AE indicator packs (Task 1 + 1b + 4 + 5).

Task 1: pack_bridge
Task 1b: run layout, docker cleanup, runner (with guaranteed finally cleanup)
Task 4: harbor_run_job + k-trial mapping docs
Task 5: import_rewards (reward -> DiagnosisReport shaped)
"""

from .docker_cleanup import cleanup_docker_for_job
from .import_rewards import import_harbor_run, reward_dir_to_report
from .pack_bridge import prepare_workspace, score_workspace, write_reward
from .run_layout import (
    finalize_meta,
    harbor_run_dir,
    init_run,
    persist_logs,
    persist_reward,
    persist_trajectory,
)
from .runner import run_harbor_task

__all__ = [
    "prepare_workspace",
    "score_workspace",
    "write_reward",
    # 1b
    "init_run",
    "persist_reward",
    "persist_trajectory",
    "persist_logs",
    "finalize_meta",
    "harbor_run_dir",
    "cleanup_docker_for_job",
    "run_harbor_task",
    # 5
    "reward_dir_to_report",
    "import_harbor_run",
]
