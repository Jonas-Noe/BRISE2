from typing import Tuple, Dict

from configuration_selection.model.optimizer.optimizer_abs import Optimizer
from tools.reflective_class_import import reflective_class_import

from reconfiguration.orchestrator import Orchestrator


class OptimizerOrchestrator(Orchestrator[Optimizer]):

    def __init__(self, description, *args):
        super().__init__("Optimizer", "configuration_selection/model/optimizer", description, *args)

    def _create_class_instance(self, description, *args):
        keys = list(description['Instance'].keys())

        assert len(keys) == 1
        assert len(args) == 2

        feature_name = keys[0]
        region = args[0]
        objectives = args[1]

        optimizer_class = self._reflective_class_import(class_name=description["Instance"][feature_name]["Type"])

        return optimizer_class(description, region, objectives)

    def get_optimizer(self, optimizer_description: Dict, region: Tuple, objectives: Dict) -> Optimizer:
        keys = list(optimizer_description['Instance'].keys())
        assert len(keys) == 1
        feature_name = keys[0]
        optimizer_class = reflective_class_import(class_name=optimizer_description["Instance"][feature_name]["Type"],
                                                  folder_path="configuration_selection/model/optimizer")

        return optimizer_class(optimizer_description, region, objectives)
