"""OpsArena Task Registry."""
from typing import Dict, List
from .base import TaskInstance
from .scenarios import (
    build_cache_pressure_task,
    build_bad_deployment_task,
    build_db_pool_exhaustion_task,
    build_downstream_timeout_task,
    build_cascading_failure_task,
    build_canary_leak_task,
    build_cost_slo_rescue_task,
    build_migration_lock_task,
)

BUILDERS = {
    "task_01_cache_pressure": build_cache_pressure_task,
    "task_02_bad_deployment": build_bad_deployment_task,
    "task_03_db_pool_exhaustion": build_db_pool_exhaustion_task,
    "task_04_downstream_timeout": build_downstream_timeout_task,
    "task_05_cascading_failure": build_cascading_failure_task,
    "task_06_canary_leak": build_canary_leak_task,
    "task_07_cost_slo_rescue": build_cost_slo_rescue_task,
    "task_08_migration_lock": build_migration_lock_task,
}

TASKS: List[str] = list(BUILDERS.keys())
DEMO_TASK: str = "task_02_bad_deployment"

def build_task(task_id: str, seed: int = 0) -> TaskInstance:
    """Builds and returns a deterministic TaskInstance for the given task_id and seed."""
    if task_id not in BUILDERS:
        raise ValueError(f"Unknown task_id '{task_id}'. Available: {', '.join(TASKS)}")
    return BUILDERS[task_id](seed)
