import abc
import os
from typing import Any

class BaseRunner(abc.ABC):
    @abc.abstractmethod
    def check_installed(self) -> bool:
        """Returns True if the required dependencies and models are installed."""
        pass

    @abc.abstractmethod
    def load(self, model_dir: str, device: str = "cuda"):
        pass
        
    @abc.abstractmethod
    def predict(self, *args, **kwargs) -> Any:
        pass
        
    @abc.abstractmethod
    def unload(self):
        pass

class ModelNotInstalledError(RuntimeError):
    pass
