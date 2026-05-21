from tools.reflective_class_import import reflective_class_import
from reconfiguration.effector import Effector
from typing import TypeVar

T = TypeVar("T")

class Orchestrator(Effector[T]):
    """Base class for all orchestrators. Allows to change the current selected strategy/component"""

    def __init__(self, variability_point, folder_path, description, *args, identifiers=None):
        self.folder_path = folder_path
        super().__init__(variability_point, description, *args, identifiers=identifiers)

    def _reflective_class_import(self, class_name:str, reduction_step:float=0.1):
        return reflective_class_import(class_name=class_name, folder_path=self.folder_path, reduction_step=reduction_step)