from tools.reflective_class_import import reflective_class_import
from typing import TypeVar, Generic

T = TypeVar("T")

class Orchestrator(Generic[T]):
    """Base class for all orchestrators. Allows to change the current selected strateg/component"""

    orchestrators = []

    def __init__(self, variability_point:str, folder_path:str, description, *args):
        """Inits the orchestrator. ``args`` will be saved and reused when strategies are changed."""
        # Orchestrator data
        self.variability_point = variability_point
        self.folder_path = folder_path

        #description = description[self.variability_point] # Maybe to avoid double typing??

        # Currently active component with args
        self._current_component = self._create_class_instance(description, *args)
        self._args = args

        #ReconfigurationExecutor.register_orchestrator(self)
        Orchestrator.orchestrators.append(self)
    
    def change_component(self, description):
        """Change the stored component"""
        assert self._current_component is not None, "Orchestrator is not initialized yet. Call init() first!"
        self._current_component = self._create_class_instance(description, *self._args)

    def get(self) -> T:
        """Return the currently used component for this variability point"""
        return self._current_component

    def _create_class_instance(self, description, *args) -> T:
        """Overwrite to define behaviour of class/component creation"""
        raise NotImplementedError("The method _create_class_instance needs to be implemented!")

    def _reflective_class_import(self, class_name:str, reduction_step:float=0.1):
        return reflective_class_import(class_name=class_name, folder_path=self.folder_path, reduction_step=reduction_step)
    
    @classmethod
    def get_all_orchestrators(cls):
        return cls.orchestrators