import os
import json
import time
import psutil
import pika
import logging

from threading import Thread

from tools.singleton import Singleton
from configuration_selection.configuration_selection import ConfigurationSelection

from tools.rabbitmq_common_tools import RabbitMQConnection, publish

from reconfiguration.monitoring.monitorable import Monitorable
from reconfiguration.effector import Effector

from core_entities.experiment import Experiment
from configuration_selection.model.predictor import Predictor
from configuration_selection.model.model import Model
from configuration_selection.sampling.selection_algorithm_abs import SamplingStrategy
from configuration_selection.model.surrogate.surrogate_abs import Surrogate
from configuration_selection.model.optimizer.optimizer_abs import Optimizer
from configuration_selection.model.candidate_selector.candidate_selector_abs import CandidateSelector
from configuration_selection.model.validator.validator_abs import Validator

class MonitorData():
    def __init__(self, monitor_or_id:Monitorable|int, comp_data:dict):
        is_monitor = not isinstance(monitor_or_id, int)

        self.obj_id = id(monitor_or_id) if is_monitor else 0
        self.key = comp_data["key"]
        self.active = comp_data["active"]
        self.region = comp_data.get("region", None)
        self.comp_data = dict([(k, v) for k, v in comp_data.items() if k not in ["key", "active", "region"]]) # Add additonal comp data (maybe create a class attribute out of them?)
        self.obj_class = monitor_or_id.__class__.__name__ if is_monitor else ""
        self.created = monitor_or_id._created if is_monitor else int(time.time() * 1000)

        self.attributes = {}

        # TODO: Remove check for whitelist
        if is_monitor and monitor_or_id._whitelist is not None:
            for name, v in monitor_or_id.get_attributes().items():
                self.attributes[name] = {"values": [self._time_stamped_value(v)]}
                self.attributes[name].update(monitor_or_id.get_attribute_data(name)) # Add attribute meta data
            #print(self.attributes)

        self.runtimes = {}

    def add_attribute_change(self, name:str, value, old_value=None, value_type=None):
        """Register a new attribute change and returns the front-end event. Setting the value type with this method only works during init via this module!"""
        event = self._event_header("attribute_change", {"name": name, "old_value": old_value})
        
        if name not in self.attributes:
            self.attributes[name] = {"value_type": value_type, "values": []}

        self.attributes[name]["values"].append(self._time_stamped_value(value))

        event.update(self.attributes[name]["values"][-1])
        return event

    def add_runtime(self, name:str, duration):
        """Add a new runtime and return the front-end event"""
        event = self._event_header("runtime", {"name": name})

        # Add runtime
        if name not in self.runtimes:
            self.runtimes[name] = []

        self.runtimes[name].append(self._time_stamped_value(duration))

        event.update(self.runtimes[name][-1]) # Add value and timestamp 
        return event

    def _time_stamped_value(self, value):

        # Take string values from complex objects
        if not isinstance(value, (str, int, float))\
            and not (isinstance(value, list) and all([isinstance(e, (str, int, float)) for e in value])):
            value = str(value)

        return {"value": value, "timestamp": int(time.time() * 1000)}

    def _event_header(self, event_type:str, data:dict|None=None):
        """Return a dict with the front-end event header"""
        e = {"type": event_type, "obj_id": self.obj_id, "key": self.key}

        if data is not None:
            e.update(data)

        return e

    def __str__(self):
        return "MonitorData: " + ", ".join([k + ": " + str(v) for k, v in self.__dict__.items() if k != "attributes"])


class ReconfigurationMonitor(metaclass=Singleton):

    # For testing (TODO: Remove?)
    run_event_service = False

    def __init__(self, cs:ConfigurationSelection):
        self.cs = cs
        self.logger = logging.getLogger(__name__)
        self._syncing = False
        self._buffered_events = []

        # Data
        self.monitor_data = {
            0: MonitorData(0, {"key": "General", "active": True})
        }

        self._load_inital_data()

        # Activate monitors
        Monitorable.active = True

        if os.environ.get('TEST_MODE') != 'UNIT_TEST' or ReconfigurationMonitor.run_event_service:
            self.connection_thread = self._EventServiceConnection(self, cs.experiment.unique_id)
            self.connection_thread.start()

    def _load_inital_data(self):
        """Load data from existing monitorable objects and build data"""        
        for monitor in Monitorable.instances:
            cls_name = monitor.__class__.__name__
            print(cls_name)

            # Construct inital monitor data
            self.monitor_data[id(monitor)] = MonitorData(monitor, self._lookup_comp(monitor))
            print(self.monitor_data[id(monitor)])

        Monitorable.instances.clear()

        # Load general info
        generalData = self.monitor_data[0]
        generalData.add_attribute_change("Start Time", int(time.time() * 1000), value_type="timestamp")
        self._update_general_data()

        # Demo
        generalData.add_attribute_change("Operator", "none")
        generalData.add_attribute_change("Operator", "Marry Smith")
        generalData.add_attribute_change("Operator", "John Doe")

    def _lookup_comp(self, comp):
        """Collect data about the monitored component. Returns a dict with the keys `vp` (variation point), `active` (component currently in use)."""
        default = {"key": None, "active": True}

        if isinstance(comp, Experiment):
            return {"key": "Experiment", "active": self.cs.experiment == comp}

        if isinstance(comp, Predictor):
            return {"key": "Predictor", "active": self.cs.predictor == comp}

        if isinstance(comp, Model):
            return {"key": "Predictor." + comp.model_name,
                    "active": comp in self.cs.predictor.mapping_region_model.values(),
                    "region": comp.region[0].name}

        if isinstance(comp, Surrogate):
            for model in self.cs.predictor.mapping_region_model.values():
                for surrogate, objectives in model.mapping_surrogate_objective.items():
                    if surrogate == comp:
                        return {"key": "Predictor." + model.model_name + "." + model.get_surrogate_vp(comp),
                                "active": True,
                                "region": model.region[0].name,
                                "objectives": objectives}

            # Search for surrogate in dynamic composite surrogates
            print("Found surrogate but could not detect the origin!")
            print(comp)
            
            return default

        if isinstance(comp, Optimizer):
            for model in self.cs.predictor.mapping_region_model.values():
                for optimizer in model.mapping_optimizer_objective.keys():
                    if optimizer == comp:
                        return {"key": "Predictor." + model.model_name + "." + model.get_optimizer_vp(comp),
                                "active": True,
                                "region": model.region[0].name}
            return default

        if isinstance(comp, CandidateSelector):
            for model in self.cs.predictor.mapping_region_model.values():
                if model.candidate_selector == comp:
                    return {"key": "Predictor." + model.model_name + ".CandidateSelector",
                            "active": True,
                            "region": model.region[0].name}
            
            return default

        if isinstance(comp, Validator):
            for model in self.cs.predictor.mapping_region_model.values():
                if model.internal_validator == comp or model.external_validator == comp:
                    return {"key": "Predictor." + model.model_name + ".Validator",
                            "external": model.external_validator == comp,
                            "active": True,
                            "region": model.region[0].name}

        if isinstance(comp, SamplingStrategy):
            return {"key": "SamplingStrategy",
                    "active": comp in self.cs.predictor.mapping_region_sampling_strategy.values(),
                    "region": comp.region[0].name}

        return default

    def sync(self):
        """Called after a new set of configurations is evaluated (and a possible reconfiguration was performed).
        Update monitoring data.
        """
        # Is syncing really necessary? There should be no missmatches. So it might be enough to send events here combined.
        #self._syncing = True
        self._update_general_data(send_to_front_end=True)

        # TODO: Update component data
        # TODO: Register new monitors??

        
        # Send buffered events
        return
        self._publish_to_front_end({"type": "combined", "events": self._buffered_events})

        self._syncing = False
        assert len(self._buffered_events) == 0
        self._buffered_events.clear()


    def _update_general_data(self, send_to_front_end:bool=False):
        """Collects and updates general data of the framework, i.e. data that is not connected via a monitor."""
        generalData = self.monitor_data[0]
        events = []

        events.append(generalData.add_attribute_change("CPU", psutil.cpu_percent()))
        events.append(generalData.add_attribute_change("Memory", psutil.virtual_memory().percent))

        if not send_to_front_end:
            return

        combined = {
            "type": "combined",
            "events": events
        }

        self._publish_to_front_end(combined)

    def process_event(self, event:dict):
        """Process given event. Separated from `_on_event` to allow for direct acccess (for testing)."""
        # Validate event
        if not all(key in event.keys() for key in ["obj_id", "type"]): #"class_name", "type"
            raise Exception("Invalid monitoring event received. Missing mandatory keys! ", event)

        #print("Monitor event:", event)
        t = event["type"]
        obj_id = event["obj_id"]

        # Check if object is registered
        if obj_id not in self.monitor_data:
            raise Exception("Unable to process event. Object id not found in self.monitoring_data. Components is not registered! Event: ", event)

        # Create the front-end event template
        data_obj = self.monitor_data[obj_id]

        # Handle event types and forward to front-end
        if t == "create":
            pass
        elif t == "attribute_change":
            self._publish_to_front_end(data_obj.add_attribute_change(event["name"], event["value"], event["old_value"]))
        elif t == "runtime":
            self._publish_to_front_end(data_obj.add_runtime(event["name"], event["time_ms"]))
        else:
            self.logger.error("Tried to process unknown event: ", event)
            return

    def _publish_to_front_end(self, event:dict):
        """Publish an event to the front end queue"""
        #if self._syncing:
        #    self._buffered_events.append(event)
        #    return

        publish("", "front_monitor_queue", json.dumps(event))
        print("Published to front-end", event)

    def _on_event(self, ch, method, properties, body):
        """Receive events from queue"""
        try:
            event = json.loads(body.decode())
            self.process_event(event)
        except json.JSONDecodeError as e:
            self.logger.exception(e)

    def _on_monitor_rpc(self, ch, method, properties, body):
        """Handle incoming monitor events from the front end"""
        try:
            event = json.loads(body.decode())
            print("Received monitor_rpc event:", event)

            if "event_type" not in event:
                self.logger.warning("Invalid rpc event received: %s", event)
                return

            # Process event(s)
            event_type = event["event_type"]
            if event_type == "request_data":
                self.logger.info("Request for monitoring data received")

                #data = {"general": {"name": "test"}, "predictor": {"value": 10}}
                # Need to serialize monitor data?

                # Send back to reply_to queue of the rpc
                ch.basic_publish(exchange="",
                                 routing_key=properties.reply_to,
                                 properties=pika.BasicProperties(correlation_id=properties.correlation_id),
                                 body=json.dumps(self.monitor_data, default=vars))
                self.logger.info("Request for monitoring data send")
                return

            self.logger.warning("Unknown rpc event type \"%s\" in event %s", event_type, event)

        except json.JSONDecodeError as e:
            self.logger.exception(e)

    def send_demo_data(self):
        t = Thread(target=self.send_test_data, daemon=True)
        t.start()

    def test_exchange(self):
        self.connection_thread.join()

    def send_test_data(self):
        import time, random

        while True:
            if "Predictor" not in self.monitor_data:
                time.sleep(3)

            

            # Simulate runtime measurement
            pred = self.cs.predictor
            print("Send demo data")
            pred.start_runtime("test_runtime")
            time.sleep(random.randint(1, 2))
            pred.stop_runtime("test_runtime")

            pred.start_runtime("test_runtime_2")
            time.sleep(random.randint(1, 2))
            pred.stop_runtime("test_runtime_2")
            time.sleep(3)

            self.cs.experiment.bad_configurations_number = (self.cs.experiment.bad_configurations_number + 1) % 30
            self._update_general_data(True)
            time.sleep(1)

            #self._update_general_data()

            # Clear to not waste too much mem
            if len(self.monitor_data[id(pred)].runtimes["test_runtime"]) >= 20:
                self.monitor_data[id(pred)].runtimes.clear()
                print("Cleared data")

    class _EventServiceConnection(RabbitMQConnection):
        """
        This class is responsible for listening to X queues.
        1. `stop_components` for shutting down configuration selection module (in case of BRISE Experiment termination).
        2. `reconf_monitor_event_exchange` for getting information about monitored components.
        3. `monitor_rpc_queue` for receiving data request from the front end.
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

            self.channel.basic_consume(queue="reconf_monitor_event_exchange" + self.experiment_id, auto_ack=True,
                                        on_message_callback=self.monitor_module._on_event)

            self.channel.basic_consume(queue="monitor_rpc_queue", auto_ack=True,
                                       on_message_callback=self.monitor_module._on_monitor_rpc)
            
            self.channel.basic_consume(queue=self.termination_queue_name, auto_ack=True,
                                        on_message_callback=self.stop)

    
