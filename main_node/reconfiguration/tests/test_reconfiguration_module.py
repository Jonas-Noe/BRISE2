import pytest
from reconfiguration.reconfigure_module import ReconfigureModule
from core_entities.experiment import Experiment
from core_entities.search_space import SearchSpace
from configuration_selection.configuration_selection import ConfigurationSelection
from configuration_selection.sampling.sobol_sequence import SobolSequence

class TestReconfigurationModule:
    
    def test_change_sampling_strategy(self, get_experiment):
        experiment_description, search_space = get_experiment(0)
        experiment = Experiment(experiment_description, search_space)
        cs = ConfigurationSelection(experiment)

        reconf = ReconfigureModule(experiment, cs)

        first_key = list(cs.predictor.get().mapping_region_sampling_strategy.keys())[0]
        sampling_old = cs.predictor.get().mapping_region_sampling_strategy[first_key]

        reconf.change_variant("SamplingStrategy", {'Sobol': {'Seed': 1, 'Type': 'sobol'}})
        reconf.reconfigure()

        sampling_new = cs.predictor.get().mapping_region_sampling_strategy[first_key]

        assert sampling_old != sampling_new
        assert isinstance(sampling_new, SobolSequence)