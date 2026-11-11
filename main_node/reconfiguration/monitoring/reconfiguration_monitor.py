import os
import json
import time
import psutil
import pika
import logging
import gc

from threading import Thread, Lock

from tools.singleton import Singleton
from configuration_selection.configuration_selection import ConfigurationSelection

from tools.rabbitmq_common_tools import RabbitMQConnection, publish

from reconfiguration.monitoring.monitorable import Monitorable
from reconfiguration.monitoring.monitor_data import MonitorData
from reconfiguration.monitoring.sending_queue import SendingQueue

from core_entities.experiment import Experiment
from configuration_selection.model.predictor import Predictor
from configuration_selection.model.model import Model
from configuration_selection.sampling.selection_algorithm_abs import SamplingStrategy
from configuration_selection.model.surrogate.surrogate_abs import Surrogate
from configuration_selection.model.surrogate.composite_surrogate import CompositeSurrogate
from configuration_selection.model.optimizer.optimizer_abs import Optimizer
from configuration_selection.model.candidate_selector.candidate_selector_abs import CandidateSelector
from configuration_selection.model.validator.validator_abs import Validator

class ReconfigurationMonitor(metaclass=Singleton):

    sync_lock = Lock() # Currently global for potential use for creation of monitorables (need to go somewhere else though)

    def __init__(self, cs:ConfigurationSelection):
        self.cs = cs
        self.logger = logging.getLogger("monitor_logger")#__name__

        # Data
        self.monitor_data = {
            0: MonitorData(0, {"key": "General", "active": True})
        }

        self.not_synced = []
        #self._send_queue = SendingQueue("front_monitor_queue", msg_combine=lambda events: {"type": "combined", "events": events})

        self._load_inital_data()

        # Activate monitors
        #self._send_queue.start()
        Monitorable.active = True

        if os.environ.get('TEST_MODE') != 'UNIT_TEST':
            self.connection_thread = self._EventServiceConnection(self, cs.experiment.unique_id)
            self.connection_thread.start()

    def _load_inital_data(self):
        """Load data from existing monitorable objects and build data"""        
        self._register_monitors(send_to_front_end=False)

        # Load general info
        generalData = self.monitor_data[0]
        generalData.add_attribute_change("Start Time", int(time.time() * 1000), value_type="timestamp")
        self._update_general_data()

        # Demo
        generalData.add_attribute_change("Operator", "none")
        generalData.add_attribute_change("Operator", "Marry Smith")
        generalData.add_attribute_change("Operator", "John Doe")

    def _register_monitors(self, send_to_front_end=True):
        """Register created monitors and rescan monitors for potential replaces"""
        new_monitors = []
        events = []
        processed = []
        
        for monitor in Monitorable.instances.copy():
            cls_name = monitor.__class__.__name__
            print(cls_name)
            processed.append(monitor)
            
            id_ = id(monitor)
            if id_ in self.monitor_data:
                # Mark monitor as synced (data is already added and up to date in this module but front-end never received anything for this monitor)
                if id_ not in self.not_synced:
                    self.logger.error("Monitor should not longer be saved in Monitorable.instances: %s", monitor)
                    raise Exception("Monitor should not be registered! Code bug!", monitor)

                self.not_synced.remove(id_) # Allow front-end events
                events.append(self._create_monitor_create_event(monitor))
                continue

            # Construct monitor data
            events.append(self._create_monitor_data(monitor, send_to_front_end=send_to_front_end))
            new_monitors.append(self.monitor_data[id_])
            
            self.logger.info("New monitor data: %s", self.monitor_data[id_])

        for monitor in processed:
            Monitorable.instances.remove(monitor) # Dont override to avoid race conditions (add a lock for monitorable creation?)
        
        self.logger.warning("Unregistered instances: %s", len(Monitorable.instances))
        self.logger.info("New monitors registered: %s", str(len(new_monitors)))

        if send_to_front_end and len(events) > 0:
            self._publish_to_front_end(events)

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

        if isinstance(comp, CompositeSurrogate):
            return {"key": "Predictor." + comp.model_name + ".CompositeSurrogate",
                    "active": False,
                    "region": comp.region[0].name,
                    "objectives": comp.objectives}

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
            #raise Exception("Unknown surrogate monitor created!", comp)
            #return default

        if isinstance(comp, Optimizer):
            for model in self.cs.predictor.mapping_region_model.values():
                for optimizer in model.mapping_optimizer_objective.keys():
                    if optimizer == comp:
                        return {"key": "Predictor." + model.model_name + "." + model.get_optimizer_vp(comp),
                                "active": True,
                                "region": model.region[0].name}
            #return default

        if isinstance(comp, CandidateSelector):
            for model in self.cs.predictor.mapping_region_model.values():
                if model.candidate_selector == comp:
                    return {"key": "Predictor." + model.model_name + ".CandidateSelector",
                            "active": True,
                            "region": model.region[0].name}
            
            #return default

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

        raise Exception("Unable to look up monitorable instance!", comp)
        print("Unable to look up comp!")
        return default

    def sync(self):
        """Called after a new set of configurations is evaluated (and a possible reconfiguration was performed).
        Update monitoring data.
        """
        with ReconfigurationMonitor.sync_lock:
            self.logger.info("Sync monitor data...")
            self.logger.info("Unsynced monitors: %s", len(self.not_synced))

            self._update_general_data(send_to_front_end=True)

            # TODO: Update component data
            self._register_monitors()

            self.logger.info("Unsynced monitors after: %s", len(self.not_synced))

    def _update_general_data(self, send_to_front_end:bool=False):
        """Collects and updates general data of the framework, i.e. data that is not connected via a monitor."""
        generalData = self.monitor_data[0]
        events = []

        events.append(generalData.add_attribute_change("CPU", psutil.cpu_percent()))
        events.append(generalData.add_attribute_change("Memory", psutil.virtual_memory().percent))

        if not send_to_front_end:
            return

        self._publish_to_front_end(events)

    def process_event(self, event:dict):
        """Process given event. Separated from `_on_event` to allow for direct acccess (for testing)."""
        # Validate event
        if not all(key in event.keys() for key in ["obj_id", "type"]):
            raise Exception("Invalid monitoring event received. Missing mandatory keys! ", event)

        with ReconfigurationMonitor.sync_lock:
            t = event["type"]
            obj_id = event["obj_id"]

            self.logger.debug("Received event: %s", event)
            self.logger.info("Received event! Should not be while syncing!")

            # Check if object is registered
            if obj_id not in self.monitor_data:
                monitor_matches = list(filter(lambda i: id(i) == obj_id, Monitorable.instances))

                # No unregistered monitor found for this event
                if len(monitor_matches) == 0:
                    self.logger.warning("MonitorData not found! Event: %s ID: %s Instances: %s", event, obj_id, len(Monitorable.instances))
                    return
                    raise Exception("Unable to process event. Object id not found in self.monitoring_data. Component is not registered! Event: ", event)

                # Create monitor data
                monitor = monitor_matches[0]
                #Monitorable.instances.remove(monitor)

                self._create_monitor_data(monitor, send_to_front_end=False)
                self.not_synced.append(obj_id)
                self.logger.debug("Added previously unregistered monitor", self.monitor_data[obj_id])

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

    def _create_monitor_data(self, monitor:Monitorable, send_to_front_end=True):
        """Create and add the monitor data and return the front-end creation event"""
        obj_id = id(monitor)

        self.monitor_data[obj_id] = MonitorData(monitor, self._lookup_comp(monitor))
        event = self._create_monitor_create_event(monitor)
        
        if not send_to_front_end:
            return event
        
        self._publish_to_front_end(event)
        return event

    def _create_monitor_create_event(self, monitor:Monitorable):
        """Return the front-end create event for a montitor that already has data in self.monitoring_data"""
        obj_id = id(monitor)

        try:
            return {"type": "create",
                    "obj_id": obj_id,
                    "data": json.dumps(self.monitor_data[obj_id], default=vars)}
        except Exception as e:
            raise Exception("WARNING: EXCEPTION when serializing monitor data", e, str(self.monitor_data[obj_id]))
        
    def _publish_to_front_end(self, events:dict|list[dict]):
        """Publish an event to the front end queue"""
        # Combine events if necessary
        event = events if isinstance(events, dict) else {"type": "combined", "events": events}

        # Prevent events from unsynced monitors
        if event["type"] not in ["create", "combined"]:
            if event["obj_id"] in self.not_synced:
                return

        publish("", "front_monitor_queue", json.dumps(event))
        #print("Published to front-end", event)

        return

        # Test send queue
        if isinstance(events, dict):
            self._send_queue.add_msg(events)
            return

        # Dont combined them multiple times (only here because other logic still there)
        for e in events:
            self._send_queue.add_msg(e)

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

    def send_coruppted_data(self):
        import random

        while True:
            if 0 not in self.monitor_data:
                time.sleep(3)

            general = self.monitor_data[0]
            event_one = general.add_attribute_change("CPU", random.randint(10, 20))
            time.sleep(0.5)
            event_two = general.add_attribute_change("CPU", random.randint(21, 30))
            time.sleep(0.5)
            event_three = general.add_attribute_change("CPU", random.randint(31, 40))
            time.sleep(0.5)

            self._publish_to_front_end(event_one)
            self._publish_to_front_end(event_three) # Send before two
            self._publish_to_front_end(event_one)  # Duplication (should be omitted) (Check for later or equal timestamp of last entry)
            self._publish_to_front_end(event_two) # Should be sorted again? (Charts and Tables sort them anyway...) -> Yes but then easier to check for duplicates?

            time.sleep(5)

    def test_sending_queue(self):
        import random
        
        while True:
            if 0 not in self.monitor_data:
                print("NOOO wait")
                time.sleep(3)

            general = self.monitor_data[0]

            for _ in range(5):
                self._publish_to_front_end(general.add_attribute_change("CPU", random.randint(10, 30)))
                self._publish_to_front_end(general.add_attribute_change("Memory", random.randint(10, 30)))
                time.sleep(0.1)

            print("Published 10 events")
            time.sleep(3)

    def send_test_data(self):
        import random

        while True:

            # Simulate runtime measurement
            pred = self.cs.predictor
            if id(pred) not in self.monitor_data:
                time.sleep(3)
                continue


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

    
