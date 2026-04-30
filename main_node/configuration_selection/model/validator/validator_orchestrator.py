from typing import Dict, Tuple

from configuration_selection.model.validator.validator_abs import Validator
from tools.reflective_class_import import reflective_class_import

from reconfiguration.orchestrator import Orchestrator

class ValidatorOrchestrator(Orchestrator[Validator]):

    def __init__(self, description, *args):
        super().__init__("Validator", "configuration_selection/model/validator", description, *args)

    def _create_component(self, description, *args):
        keys = list(description.keys())

        assert len(keys) == 1
        assert len(args) == 2

        feature_name = keys[0]

        region = args[0]
        objectives = args[1]

        validator_class = self._reflective_class_import(description[feature_name]["Type"])
        return validator_class(description[feature_name], region, objectives)

    def get_validator(self, validator_description: Dict, region: Tuple, objectives: Dict) -> Validator:
        keys = list(validator_description.keys())
        assert len(keys) == 1
        feature_name = keys[0]

        validator_class = reflective_class_import(validator_description[feature_name]["Type"], "configuration_selection/model/validator")
        return validator_class(validator_description[feature_name], region, objectives)
