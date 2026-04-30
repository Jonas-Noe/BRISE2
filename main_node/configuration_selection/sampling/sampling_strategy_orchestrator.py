from configuration_selection.sampling.selection_algorithm_abs import SamplingStrategy
from tools.reflective_class_import import reflective_class_import
from reconfiguration.orchestrator import Orchestrator

class SamplingStrategyOrchestrator(Orchestrator[SamplingStrategy]):

    def __init__(self, description, *args):
        super().__init__("SamplingStrategy", "configuration_selection/sampling", description, *args)

    def _create_component(self, description, *args):
        keys = list(description.keys())
        
        assert len(keys) == 1
        assert len(args) == 1

        feature_name = keys[0]
        region = args[0]

        strategy_class = self._reflective_class_import(class_name=description[feature_name]["Type"])

        return strategy_class(description[feature_name], region)

    def get_sampling_strategy(self, sampling_strategy_description: tuple, region: tuple) -> SamplingStrategy:
        """
        Returns instance of selection algorithm with provided data
        :param sampling_strategy_description: sampling strategy description.
        :param region: region which is handled by the sampling strategy.
        :return: sampling strategy object
        """
        keys = list(sampling_strategy_description.keys())
        
        assert len(keys) == 1
        feature_name = keys[0]
        sampling_strategy_class = reflective_class_import(class_name=sampling_strategy_description[feature_name]["Type"],
                                                 folder_path="configuration_selection/sampling")

        return sampling_strategy_class(sampling_strategy_description[feature_name], region)
