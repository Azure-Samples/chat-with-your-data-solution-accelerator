import os
from typing import List
import os.path
import pkgutil
from .orchestration_strategy import OrchestrationStrategy


class OrchestrationSettings:
    def __init__(self, orchestration: dict):
        self.strategy = OrchestrationStrategy(orchestration["strategy"])


# Get a list of all the classes defined in the module
def get_all_classes() -> List[str]:
    return [name for _, name, _ in pkgutil.iter_modules([os.path.dirname(__file__)])]


__all__ = get_all_classes()
