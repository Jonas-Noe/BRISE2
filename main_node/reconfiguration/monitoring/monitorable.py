import json
import time
from abc import ABCMeta

from tools.rabbitmq_common_tools import publish

class Monitorable:
    """Monitors all changes in the object"""

    experiment_id = None
    active = False

    instances = [] # Temporarly save instances until there are processed

    def __init__(self):
        self._runtimes = {} # Keeps track of current runtime measurements
        self._ignore_attributes = ["_ignore_attributes", "_runtimes", "instances", "experiment_id", "active"]

        Monitorable.instances.append(self)            

    def __setattr__(self, name, value):
        """Added default behavior to notify on value change. Does not affect lists, dicts, etc."""
        try:
            if (hasattr(self, name) and getattr(self, name) != value):
                self.value_changed(name, value, old_value=getattr(self, name))
        except Exception as e:
            print("WARNING: Exception in monitorable:", e)

        super().__setattr__(name, value)

    def value_changed(self, name, value, old_value=None):
        """Send a attribute change event. Old value may be None"""
        if not Monitorable.active:
            return

        print(f"Monitor: {name} changed to {value}")

        event = {"type": "attribute_change", "attr": name, "value": value, "old_value": old_value}
        self.publish_event(event)

    def monitor_runtime(name:str|None=None):
        """Decorator to register a function for runtime monitoring"""
        def monitor_runtime(func):
            def inner(self:Monitorable, *args, **kwargs):
                if not Monitorable.active:
                    return func(self, *args, **kwargs)
                
                start = time.time()
                ret_val = func(self, *args, **kwargs)
                duration = time.time() - start
                
                event = {
                    "type": "func_runtime",
                    "func_name": func.__name__,
                    "time_ms": duration / 1000,
                    "name": name if name is not None else ""
                }
        
                self.publish_event(event)
                return ret_val
            return inner
        return monitor_runtime

    def start_runtime(self, name:str):
        """Start the a runtime measurement"""
        self._runtimes[name] = time.time()

    def stop_runtime(self, name:str):
        """End and send runtime measurement"""
        if name not in self._runtimes:
            raise Exception("Runtime measurement %s was never started", name)

        duration = (time.time() - self._runtimes[name])
        event = {
            "type": "runtime",
            "time_ms": duration / 1000,
            "name": name
        }

        del self._runtimes[name]
        self.publish_event(event)

    def get_attributes(self):
        """Return a dict with all class attributes for monitoring"""
        attributes = {}
        
        # Find valid attributes to monitor
        for attr, v in self.__dict__.items():
            if attr in self._ignore_attributes or callable(v):
                continue

            attributes[attr] = v

        return attributes

    def publish_event(self, event:dict):
        """Publish a monitor event. (Overwrite for unit tests)"""
        if Monitorable.experiment_id is None:
            raise Exception("experiment_id of this class must be set")

        if not Monitorable.active:
            return

        event.update({
            "obj_id": id(self),
            "class_name": str(type(self).__name__),
            "class_str": str(self)
        })
        
        print("Monitor Event:", event)
        publish("reconf_monitor_event_exchange", Monitorable.experiment_id, json.dumps(event))

class MonitorableABC(Monitorable, metaclass=ABCMeta):
    __slots__ = ()

    def __init__(self):
        super().__init__()