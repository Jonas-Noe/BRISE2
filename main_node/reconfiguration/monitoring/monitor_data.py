import time

from reconfiguration.monitoring.monitorable import Monitorable

class MonitorData():
    """Holds collected data of a monitorable object. Itself is no longer linked to it to allowed it to be deleted by the gc."""
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

    def add_attribute_change(self, name:str, value, old_value=None, value_type=None, unit=None):
        """Register a new attribute change and returns the front-end event. Setting the value type or unit with this method only works during init via this module!"""
        event = self._event_header("attribute_change", {"name": name, "old_value": old_value})
        
        if name not in self.attributes:
            self.attributes[name] = {"value_type": value_type, "unit": unit, "values": []}

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
        """Converts the value into a dict with `value` and `timestamp` as key."""
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