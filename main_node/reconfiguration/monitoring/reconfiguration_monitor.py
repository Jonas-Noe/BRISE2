import os
import json
import time

from tools.singleton import Singleton
from configuration_selection.configuration_selection import ConfigurationSelection

from tools.rabbitmq_common_tools import RabbitMQConnection

from reconfiguration.monitoring.monitorable import Monitorable
from reconfiguration.effector import Effector

from configuration_selection.model.predictor import Predictor
from configuration_selection.model.model import Model
from configuration_selection.sampling.selection_algorithm_abs import SamplingStrategy
from configuration_selection.model.surrogate.surrogate_abs import Surrogate
from configuration_selection.model.optimizer.optimizer_abs import Optimizer
from configuration_selection.model.candidate_selector.candidate_selector_abs import CandidateSelector
from configuration_selection.model.validator.validator_abs import Validator

class MonitorData():
    def __init__(self, monitor:Monitorable, key:str, comp_data:dict):
        self.obj_id = id(monitor)
        self.key = key

        self.attributes = {}

        #for name, v in monitor.get_attributes().items():
        #    self.attributes[name] = self._time_stamped_value(v)

        self.runtimes = {}

    def add_attribute_change(self, name, value, old_value=None):
        """Register a new attribute change and returns the saved data"""
        if name not in self.attributes:
            self.attributes[name] = [self._time_stamped_value(value)]
            return

        self.attributes[name].append(self._time_stamped_value(value))
        return self.attributes[name][-1]

    def add_runtime(self, name):
        pass

    def _time_stamped_value(self, value):
        return {"value": value, "time": time.time()}

    def __str__(self):
        return "MonitorData: " + ", ".join([k + ": " + str(v) for k, v in self.__dict__.items()])


class ReconfigurationMonitor(metaclass=Singleton):

    data_stucture = {
        Predictor: "Predictor",
        Model: "Predictor.Model",
        Surrogate: "Predictor.Model.Surrogate",
        Optimizer: "Predictor.Model.Optimizer",
        CandidateSelector: "Predictor.Model.CandidateSelector",
        Validator: "Predictor.Model.Validator",
        SamplingStrategy: "SamplingStrategy"
    }

    def __init__(self, cs:ConfigurationSelection):
        self.cs = cs

        # Data
        self.monitor_data = {}
        self._load_inital_data()

        # Activate monitors
        Monitorable.active = True

        if os.environ.get('TEST_MODE') != 'UNIT_TEST':
            self.connection_thread = self._EventServiceConnection(self, cs.experiment.unique_id)
            self.connection_thread.start()

    def _load_inital_data(self):
        """Load data from existing monitorable objects and build data"""
        desc = self.cs.experiment.description["ConfigurationSelection"]

        # 1. Idea identify VP/name in desc by class/module name
        #       - Match 
        
        for monitor in Monitorable.instances:
            cls = monitor.__class__
            cls_name = cls.__name__
            cls_module = str(cls.__module__).replace("configuration_selection.model.", "")
            base_vp_name = "".join([s.capitalize() for s in cls_module.split(".")[0].split("_")])
            print(cls_name, cls_module, base_vp_name)

            key = None

            for cls_type, k in ReconfigurationMonitor.data_stucture.items():
                if isinstance(monitor, cls_type):
                    key = k
                    print("Found match", cls_type.__name__)
                    break

            if key is None:
                print("NO MATCH found for:", monitor)
                continue

            # Construct inital monitor data
            self.monitor_data[id(monitor)] = MonitorData(monitor, key, self.lookup_comp(monitor))
            print(self.monitor_data[id(monitor)])

        Monitorable.instances.clear()

    def lookup_comp(self, comp):
        default = {"vp": None, "active": True}

        if isinstance(comp, Predictor):
            return {"vp": "Predictor", "active": self.cs.predictor == comp}

        if isinstance(comp, Model):
            return {"vp": comp.model_name, "active": comp in self.cs.predictor.mapping_region_model.values()}

        if isinstance(comp, Surrogate):
            for model in self.cs.predictor.mapping_region_model.values():
                for surrogate in model.mapping_surrogate_objective.keys():
                    if surrogate == comp:
                    #if surrogate.surrogate_description == comp.surrogate_description:
                        return {"vp": model.model_name + "." + model.get_surrogate_vp(comp), "active": True}

            # Search for surrogate in dynamic composite surrogates
            
            return default

        if isinstance(comp, Optimizer):
            for model in self.cs.predictor.mapping_region_model.values():
                for optimizer in model.mapping_optimizer_objective.keys():
                    if optimizer == comp:
                        return {"vp": model.model_name + "." + model.get_optimizer_vp(comp), "active": True}
            return default

        if isinstance(comp, CandidateSelector):
            for model in self.cs.predictor.mapping_region_model.values():
                if model.candidate_selector == comp:
                    return {"vp": model.model_name + ".CandidateSelector", "active": True}
            
            return default

        if isinstance(comp, Validator):
            for model in self.cs.predictor.mapping_region_model.values():
                if model.internal_validator == comp or model.external_validator == comp:
                    return {"vp": model.model_name + ".Validator", "external": model.external_validator == comp, "active": True}

        if isinstance(comp, SamplingStrategy):
            return {"vp": "SamplingStrategy", "active": comp in self.cs.predictor.mapping_region_sampling_strategy.values()}

        return default

    def process_event(self, event:dict):
        """Process given event. Separated from `_on_event` to allow for direct acccess (for testing)."""
        # Validate event
        if not all(["obj_id", "class_name", "type"] in event.keys()):
            raise Exception("Invalid monitoring event received. Missing mandatory keys! %s", event)

        #print("Monitor event:", event)
        t = event["type"]

        if t == "create":
            pass
        elif t == "func_runtime":
            print("MONITOR:", event["func_name"], "of", event["object"], "took", event["time_ms"], "ms")

    def _on_event(self, ch, method, properties, body):
        """Method to receive events from queue"""
        event = json.loads(body.decode())

        self.process_event(event)

    def _get_descriptions(self, model_description:dict, type_name:str):
        """Return a list with all descriptions of a special type like Optimizer, Surrogate, etc."""
        return [description for key, description in model_description.items() if type_name in key]

    class _EventServiceConnection(RabbitMQConnection):
        """
        This class is responsible for listening to X queues.
        1. `stop_components` for shutting down configuration selection module (in case of BRISE Experiment termination).
        2. `reconf_monitor_events` for getting information about monitored components.
        """

        def __init__(self, monitor_module, experiement_id):
            """
            The function for initializing consumer thread
            """
            self.monitor_module: ReconfigurationMonitor = monitor_module
            self.experiment_id = experiement_id
            super().__init__(monitor_module)

        def bind_and_consume(self):
            self.termination_result = self.channel.queue_declare(queue='', exclusive=True)
            self.termination_queue_name = self.termination_result.method.queue
            self.channel.queue_bind(exchange='experiment_termination_exchange',
                                    queue=self.termination_queue_name,
                                    routing_key=self.experiment_id)

            self.channel.basic_consume(queue="reconf_monitor_events" + self.experiment_id, auto_ack=True,
                                        on_message_callback=self.monitor_module._on_event)
            self.channel.basic_consume(queue=self.termination_queue_name, auto_ack=True,
                                        on_message_callback=self.stop)
    
