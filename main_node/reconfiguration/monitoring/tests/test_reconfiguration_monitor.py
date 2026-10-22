import pytest
import os

from core_entities.experiment import Experiment
from configuration_selection.configuration_selection import ConfigurationSelection

from reconfiguration.monitoring.monitorable import Monitorable
from reconfiguration.monitoring.reconfiguration_monitor import ReconfigurationMonitor
from reconfiguration.reconfiguration_module import ReconfigurationModule
from reconfiguration.effector import Effector

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

        experiment_description, search_space = get_experiment(experiment_num)
        experiment = Experiment(experiment_description, search_space)
        TestReconfigurationMonitor.cs = ConfigurationSelection(experiment) # Save to avoid that effectors are cleared!
        rm = ReconfigurationModule(experiment) # TODO: Probably needed later on
        return ReconfigurationMonitor(TestReconfigurationMonitor.cs)

    def test_reconf_monitor_setup(self, reconf_monitor:ReconfigurationMonitor):
        """Test the processing of created monitored components"""
        #print(reconf_monitor)
        #print(reconf_monitor.monitor_data)
        assert False