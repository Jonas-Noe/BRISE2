import pytest

from reconfiguration.reconfigure_module import ReconfigureModule
from reconfiguration.effector import Effector
from core_entities.experiment import Experiment
from configuration_selection.model.model import Model
from configuration_selection.configuration_selection import ConfigurationSelection
from configuration_selection.sampling.sobol_sequence import SobolSequence
from configuration_selection.model.optimizer.moea import MOEA
from configuration_selection.model.optimizer.random_search import RandomSearch
from configuration_selection.model.surrogate.tree_parzen_estimator import TreeParzenEstimator
from configuration_selection.model.surrogate.model_mock import ModelMock

class TestReconfigurationModule:
    
    @pytest.fixture(scope='function')
    def reconf_module(self, get_experiment):
        return self._get_reconf_module(get_experiment)
    
    @pytest.fixture(scope='function')
    def reconf_module_multi_models(self, get_experiment):
        return self._get_reconf_module(get_experiment, experiment_num=8)
    
    @pytest.fixture(scope='function')
    def reconf_module_multi_features_single_model(self, get_experiment):
        return self._get_reconf_module(get_experiment, experiment_num=3)

    def _get_reconf_module(self, get_experiment, experiment_num:int = 0):
        """Make a separate function out of it to reuse it for diffrent experiment numbers"""
        #Effector.clear_all()

        experiment_description, search_space = get_experiment(experiment_num)
        experiment = Experiment(experiment_description, search_space)
        cs = ConfigurationSelection(experiment)
        return ReconfigureModule(experiment, cs)

    def test_change_sampling_strategy(self, get_experiment):
        experiment_description, search_space = get_experiment(0)
        experiment = Experiment(experiment_description, search_space)
        cs = ConfigurationSelection(experiment)

        reconf = ReconfigureModule(experiment, cs)

        first_key = list(cs.predictor.get().mapping_region_sampling_strategy.keys())[0]
        sampling_old = cs.predictor.get().mapping_region_sampling_strategy[first_key].get()

        reconf.change_variant("SamplingStrategy", {'Sobol': {'Seed': 1, 'Type': 'sobol'}})
        reconf.done().reconfigure()

        first_key = list(cs.predictor.get().mapping_region_sampling_strategy.keys())[0]
        sampling_new = cs.predictor.get().mapping_region_sampling_strategy[first_key].get()

        assert sampling_old != sampling_new
        assert isinstance(sampling_new, SobolSequence)

    def test_change_single_surrogate(self, reconf_module_multi_features_single_model:ReconfigureModule):
        reconf_module = reconf_module_multi_features_single_model
        cs = reconf_module.configuration_selection

        # Test before
        model = cs.predictor.get().mapping_region_model.popitem()[1]
        assert isinstance(model, Model)
        for so in model.mapping_surrogate_objective.keys():
            assert isinstance(so.get(), TreeParzenEstimator)

        # Change
        surrogate_desc = {"Instance": {"ModelMock": {
                            "MultiObjective": True,
                            "Type": "model_mock"
                        }
                    }}
        reconf_module.change_variant("Surrogate_0", surrogate_desc)
        reconf_module.done().reconfigure()

        # Assert change
        mock_count = 0
        tree_count = 0

        for so in model.mapping_surrogate_objective.keys():
            if isinstance(so.get(), TreeParzenEstimator):
                tree_count += 1
            elif isinstance(so.get(), ModelMock):
                mock_count += 1

        assert mock_count == 1
        assert tree_count == 4

    def test_change_single_optimizer(self, reconf_module_multi_features_single_model:ReconfigureModule):
        """Test to change a single optimizer"""
        reconf_module = reconf_module_multi_features_single_model
        cs = reconf_module.configuration_selection

        # Assert that config was loaded correctly
        assert len(cs.predictor.get().mapping_region_model) == 1

        model = cs.predictor.get().mapping_region_model.popitem()[1]
        assert len(model.mapping_optimizer_objective) == 5
        
        assert all([isinstance(optimizer.get(), MOEA) for optimizer in list(model.mapping_optimizer_objective.keys())])
        
        # Change
        optimizer_desc = {"Instance": {
                        "RandomSearch": {
                            "SamplingSize": 500,
                            "MultiObjective": True,
                            "Type": "random_search"
                        }
                    }}
        reconf_module.change_variant("Optimizer_0", optimizer_desc)
        reconf_module.done().reconfigure()

        # Assert that the change worked
        assert len(model.mapping_optimizer_objective) == 5

        moea_count = 0
        random_count = 0
        for optimizer in list(model.mapping_optimizer_objective.keys()):
            if isinstance(optimizer.get(), MOEA):
                moea_count += 1
                continue

            if isinstance(optimizer.get(), RandomSearch):
                random_count += 1

        assert moea_count == 4
        assert random_count == 1

    def test_change_single_surrogate_on_multiple_models(self, reconf_module_multi_models:ReconfigureModule):
        """Test to change a single surrogate on a experiment with multiple models"""
        reconf_module = reconf_module_multi_models
        cs = reconf_module.configuration_selection

        # Assert that config was loaded correctly
        assert len(cs.predictor.get().mapping_region_model) == 3

        model_ones = [model for model in cs.predictor.get().mapping_region_model.values() if model.model_name == "Model_1"]
        assert len(model_ones) == 2

        surrogate_types = ["LinearRegression", "GradientBoostingRegressor", "BayesianRidgeRegression", "ModelMock"]
        for model in model_ones:
            for s in list(model.mapping_surrogate_objective.keys()):
                assert s.get().feature_name in surrogate_types

        # Change
        surrogate_desc = {"Instance": {"ModelMock": {
                            "MultiObjective": True,
                            "Type": "model_mock"
                        }
                    }}
        reconf_module.change_variant("Surrogate_0", surrogate_desc, ["Model_1"])
        reconf_module.done().reconfigure()
        
        # Assert that change was correct
        surrogate_types = ["GradientBoostingRegressor", "BayesianRidgeRegression", "ModelMock"] # No LinearRegression any more
        for model in model_ones:
            for s in list(model.mapping_surrogate_objective.keys()):
                assert s.get().feature_name in surrogate_types