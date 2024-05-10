import os
from typing import List
import os.path
import pkgutil
from .strategies import LoadingStrategy


class LoadingSettings:
    def __init__(self, loading):
        self.loading_strategy = LoadingStrategy(loading["strategy"])

    def __eq__(self, other: object) -> bool:
        if isinstance(self, other.__class__):
            return self.loading_strategy == other.loading_strategy
        else:
            return False


# Get a list of all the classes defined in the module
def get_all_classes() -> List[str]:
    return [name for _, name, _ in pkgutil.iter_modules([os.path.dirname(__file__)])]


__all__ = get_all_classes()
