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
        #print(reconf_monitor)
        print(reconf_monitor.monitor_data)

        data = reconf_monitor.monitor_data
        model = list(self.cs.predictor.mapping_region_model.values())[0]

        # Constructed data correctly
        any([d.obj_class == "Predictor" and id(self.cs.predictor) == d.obj_id and d.key == "Predictor" for d in data.values()])
        any([d.obj_class == "Model" and id(model) == d.obj_id and d.key == "Predictor.Model" for d in data.values()])
        any([d.obj_class == "MOEA" and d.key == "Predictor.Model.Optimizer" for d in data.values()])
        any([d.obj_class == "MockValidator" and d.key == "Predictor.Model.Validator" for d in data.values()])
        any([d.obj_class == "BestMultiPoint" and d.key == "Predictor.Model.CandidateSelector" for d in data.values()])
        any([d.obj_class == "SobolSequence" and d.key == "SamplingStrategy" for d in data.values()])
        any([d.obj_class == "TreeParzenEstimator" and d.key == "Predictor.Model.Surrogate" for d in data.values()])

        # Cleared created instances
        assert len(Monitorable.instances) == 0

        # TODO: Adapt for more monitorbale components?

        assert False, "Nothing wrong but i want print"