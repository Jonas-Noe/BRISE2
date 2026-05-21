from typing import Tuple, Dict

from configuration_selection.model.surrogate.surrogate_abs import Surrogate
from tools.reflective_class_import import reflective_class_import
from reconfiguration.orchestrator import Orchestrator


class SurrogateOrchestrator(Orchestrator[Surrogate]):

    def __init__(self, description, *args, vp="Surrogate", identifiers=None):
        super().__init__(vp, "configuration_selection/model/surrogate", description, *args, identifiers=identifiers)

    def _create_component(self, description, *args):    
        keys = list(description['Instance'].keys())

        assert len(keys) == 1

        feature_name = keys[0]
        region = args[0]
        objectives = args[1]

        surrogate_class = self._reflective_class_import(description["Instance"][feature_name]["Type"])

        return surrogate_class(description, region, objectives)

    def get_surrogate(self, surrogate_description: Dict, region: Tuple, objectives: Dict) -> Surrogate:
        keys = list(surrogate_description['Instance'].keys())
        assert len(keys) == 1
        feature_name = keys[0]
        surrogate_class = reflective_class_import(class_name=surrogate_description["Instance"][feature_name]["Type"],
                                                  folder_path="configuration_selection/model/surrogate")

        return surrogate_class(surrogate_description, region, objectives)
