import pytest
import os

from core_entities.experiment import Experiment
from configuration_selection.configuration_selection import ConfigurationSelection

from reconfiguration.monitoring.monitorable import Monitorable
from reconfiguration.monitoring.reconfiguration_monitor import ReconfigurationMonitor
from reconfiguration.reconfiguration_module import ReconfigurationModule
from reconfiguration.effector import Effector

from tools.rabbitmq_common_tools import publish

class TestReconfigurationMonitor:

    cs = None

    @pytest.fixture(scope='function')
    def reconf_monitor(self, get_experiment):
        return self._get_reconf_monitor(get_experiment)

    @pytest.fixture(scope='function')
    def reconf_monitor_exp_8(self, get_experiment):
        return self._get_reconf_monitor(get_experiment, experiment_num=8)
    
    def _get_reconf_monitor(self, get_experiment, experiment_num:int = 0):
        """Setup the reconf monitor and load test experiment"""
        Effector.clear_all()

        # Temp: For running from VS Code
        os.environ["BRISE_DATABASE_HOST"] = "test_db"
        os.environ["BRISE_DATABASE_PORT"] = "27017"
        os.environ["BRISE_DATABASE_PASS"] = "test111"
        os.environ["BRISE_DATABASE_USER"] = "user"
        os.environ["TEST_MODE"] = "UNIT_TEST"

        # TODO: Remove!!!!
        #ReconfigurationMonitor.run_event_service = True

        experiment_description, search_space = get_experiment(experiment_num)
        experiment = Experiment(experiment_description, search_space)
        TestReconfigurationMonitor.cs = ConfigurationSelection(experiment) # Save to avoid that effectors are cleared!
        rm = ReconfigurationModule(experiment) # TODO: Probably needed later on
        return ReconfigurationMonitor(TestReconfigurationMonitor.cs)

    def test_basic_reconf_monitor_setup(self, reconf_monitor:ReconfigurationMonitor):
        """Test the processing of created monitored components"""
        data = reconf_monitor.monitor_data
        model = list(self.cs.predictor.mapping_region_model.values())[0]

        # Constructed data correctly
        assert_key_and_class_amount(data, "Predictor", "Predictor", 1)
        assert_obj_matches_monitor_obj(data, "Predictor", "Predictor", self.cs.predictor)

        assert_key_and_class_amount(data, "SamplingStrategy", "SobolSequence", 1)

        assert_key_and_class_amount(data, "Predictor.Model", "Model", 1)
        assert_obj_matches_monitor_obj(data, "Predictor.Model", "Model", model)

        assert_key_and_class_amount(data, "Predictor.Model.Optimizer", "MOEA", 1)
        assert_key_and_class_amount(data, "Predictor.Model.Validator", "MockValidator", 1)
        assert_key_and_class_amount(data, "Predictor.Model.CandidateSelector", "BestMultiPoint", 1)
        assert_key_and_class_amount(data, "Predictor.Model.Surrogate", "TreeParzenEstimator", 1)
        
        # Cleared created instances
        assert len(Monitorable.instances) == 0

        # TODO: Adapt for more monitorbale components?

        # Overall checks
        assert not any([d.key == None for d in data.values()])

    def test_complex_reconf_monitor_setup(self, reconf_monitor_exp_8:ReconfigurationMonitor):
        """Test that the setup works for complex (hierarchical) experiments"""
        reconf_monitor = reconf_monitor_exp_8

        data = reconf_monitor.monitor_data

        # 1 Predictor
        assert any([d.obj_class == "Predictor" and id(self.cs.predictor) == d.obj_id and d.key == "Predictor" for d in data.values()])
        assert_key_class_amount(data, "Predictor", "Predictor", 1)
        assert_obj_matches_monitor_obj(data, "Predictor", "Predictor", self.cs.predictor)

        # 3 times SamplingStrategy
        assert_key_and_class_amount(data, "SamplingStrategy", "SobolSequence", 3)

        # Model 1 with Surrogate, Validator, CandidateSelector, Optimizer 1 each (check for multiplaction due to multi obj)
        model_ones = [model for model in self.cs.predictor.mapping_region_model.values() if model.model_name == "Model_0"]
        assert len(model_ones) == 1 
        model_one = model_ones[0]

        ## Surrogate
        assert_key_and_class_amount(data, "Predictor.Model_0.Surrogate", "MultiArmedBandit", 1)
        assert_obj_matches_monitor_obj(data, "Predictor.Model_0.Surrogate", "MultiArmedBandit", list(model_one.mapping_surrogate_objective.keys())[0])

        ## CandidateSelector
        assert_key_and_class_amount(data, "Predictor.Model_0.CandidateSelector", "BestMultiPoint", 1)
        assert_obj_matches_monitor_obj(data, "Predictor.Model_0.CandidateSelector", "BestMultiPoint", model_one.candidate_selector)

        ## Optimizer
        assert_key_and_class_amount(data, "Predictor.Model_0.Optimizer", "RandomSearch", 1)
        assert_obj_matches_monitor_obj(data, "Predictor.Model_0.Optimizer", "RandomSearch", list(model_one.mapping_optimizer_objective.keys())[0])

        ## Validator
        assert_key_and_class_amount(data, "Predictor.Model_0.Validator", "MockValidator", 1)
        assert_obj_matches_monitor_obj(data, "Predictor.Model_0.Validator", "MockValidator", model_one.external_validator)

        # Model 2 with Optimizer, Validator (internal and external), CandidateSelector and 4 Surrogates (check for multiplaction due to multi obj)
        model_twos = [model for model in self.cs.predictor.mapping_region_model.values() if model.model_name == "Model_1"]
        assert len(model_twos) == 2

        ## Surrogate
        assert_key_and_class_amount(data, "Predictor.Model_1.Surrogate_0", "SklearnWrapper", 4) # 2 * 2 <-- 2 Models, Portfolio: Create one per objective
        assert_key_and_class_amount(data, "Predictor.Model_1.Surrogate_1", "SklearnWrapper", 4)
        assert_key_and_class_amount(data, "Predictor.Model_1.Surrogate_2", "SklearnWrapper", 4)
        assert_key_and_class_amount(data, "Predictor.Model_1.Surrogate_3", "ModelMock", 6) # + 1 per model since it is multi objective

        ## CandidateSelector
        assert_key_and_class_amount(data, "Predictor.Model_1.CandidateSelector", "RandomMultiPoint", 2)

        ## Optimizer
        assert_key_and_class_amount(data, "Predictor.Model_1.Optimizer", "RandomSearch", 2)

        ## Validator
        assert_key_and_class_amount(data, "Predictor.Model_1.Validator", "QualityValidator", 4)
        
        # Cleared created instances
        assert len(Monitorable.instances) == 0

        # Overall checks
        assert not any([d.key == None for d in data.values()])

        #assert False, "Nothing wrong"

    def test_dynamic_comp_surrogate(self, reconf_monitor_exp_5:ReconfigurationMonitor):
        """Test the creation of dynamic compositional surroagtes and implicitly the registration of dynamically created monitorables"""
        

def assert_key_and_class_amount(data:dict, key:str, obj_class:str, key_amount:int, class_amount:int=None):
    assert_key_amount(data, key, key_amount)
    assert_key_class_amount(data, key=key, obj_class=obj_class, amount=key_amount if class_amount is None else class_amount)

def assert_obj_matches_monitor_obj(data:dict, key:str, obj_class:str, compare_list:list|object):
    """Implicit incorporates `assert_key_class_amount`. Order of the compare list must match (meaning the creation order!)"""
    monitor_comps = [d for d in data.values() if d.key == key and d.obj_class == obj_class]
    compare_list = [compare_list] if not isinstance(compare_list, list) else compare_list

    assert len(monitor_comps) == len(compare_list), "Mismatching length of found monitored objects and compare list"

    for i, c in enumerate(monitor_comps):
        assert c.obj_id == id(compare_list[i])

def assert_key_amount(data:dict, key:str, amount:int):
    assert len([d for d in data.values() if d.key == key]) == amount, f'Mismatch between expected and found monitor objects with key: {key}'

def assert_key_class_amount(data:dict, key:str, obj_class:str, amount:int):
    assert len([d for d in data.values() if d.key == key and d.obj_class == obj_class]) == amount,\
        f'Mismatch between expected and found monitor objects with key {key} and obj_class {obj_class}'