from typing import Dict

from configuration_selection.model.candidate_selector.candidate_selector_abs import CandidateSelector
from tools.reflective_class_import import reflective_class_import
from reconfiguration.orchestrator import Orchestrator

class CandidateSelectorOrchestrator(Orchestrator[CandidateSelector]):

    def __init__(self, description, *args):
        super().__init__("CandidateSelector", "configuration_selection/model/candidate_selector", description, *args)

    def _create_class_instance(self, description, *args):
        keys = list(description.keys())
        assert len(keys) == 1

        feature_name = keys[0]
        print(feature_name)
        candidate_selector_class = self._reflective_class_import(description[feature_name]["Type"])

        return candidate_selector_class(description)

    def get_candidate_selector(self, candidate_selector_description: Dict) -> CandidateSelector:
        keys = list(candidate_selector_description.keys())
        assert len(keys) == 1
        feature_name = keys[0]
        candidate_selector_class = reflective_class_import(
            class_name=candidate_selector_description[feature_name]["Type"],
            folder_path="configuration_selection/model/candidate_selector")

        return candidate_selector_class(candidate_selector_description)
