import json
import time
import logging
from abc import ABCMeta

from tools.rabbitmq_common_tools import publish

class Monitorable:
    """Monitors all changes in the object"""

    experiment_id = None
    active = False
    # Set to false to ignore any registration until set to true again.
    # Monitoring functionallity for created instances will also be deactivated
    allow_registration = True 

    instances = [] # Temporarly save instances until there are processed

    def __init__(self, no_monitoring=False):
        if not Monitorable.allow_registration or no_monitoring:
            logging.getLogger("monitor_logger").info("Inactive instance created %s %s %s", self, id(self), no_monitoring)
            self.active = False
            return

        self.active = True
        self._created = int(time.time() * 1000)
        self._runtimes = {} # Keeps track of current runtime measurements

        self._attribute_data = {} # Adds additional attribute data. Keys: value_type, unit

        # Whitelist and blacklist for attribute tracking
        self._whitelist = None
        self._blacklist = ["_blacklist", "_runtimes", "_whitelist", "_attribute_data", "_created", "instances", "experiment_id", "active", "allow_registration"]

        Monitorable.instances.append(self)
        logging.getLogger("monitor_logger").info("New instance created %s %s", self, id(self))

    def __setattr__(self, name, value):
        """Added default behavior to notify on value change. Does not affect lists, dicts, etc."""
        if not self.active or not Monitorable.allow_registration:
            super().__setattr__(name, value)
            return
        
        try:
            if (hasattr(self, name) and getattr(self, name) != value):
                self.attribute_value_changed(name, value, old_value=getattr(self, name))
        except Exception as e:
            print("WARNING: Exception in monitorable:", e)

        super().__setattr__(name, value)

    def attribute_value_changed(self, name, value, old_value=None):
        """Send a attribute change event. Old value may be None"""
        if not Monitorable.active or not self.active:
            return

        # Check whitelist
        if self._whitelist is not None and name not in self._whitelist:
            return

        # Check blacklist
        if name in self._blacklist:
            return

        event = {"type": "attribute_change",
                 "name": name,
                 "value": value,
                 "old_value": old_value}
                 #"value_type": self._attribute_types[name] if name in self._attribute_types else None}
        self.publish_event(event)

    def monitor_runtime(name:str|None=None):
        """Decorator to register a function for runtime monitoring"""
        def monitor_runtime(func):
            def inner(self:Monitorable, *args, **kwargs):
                if not Monitorable.active or not self.active:
                    return func(self, *args, **kwargs)
                
                start = time.time()
                ret_val = func(self, *args, **kwargs)
                duration = time.time() - start
                
                event = {
                    "type": "runtime",
                    "time_ms": duration * 1000,
                    "name": name if name is not None else func.__name__
                }
        
                self.publish_event(event)
                return ret_val
            return inner
        return monitor_runtime

    def start_runtime(self, name:str):
        """Start the a runtime measurement"""
        if not self.active:
            return
        
        self._runtimes[name] = time.time()

    def stop_runtime(self, name:str):
        """End and send runtime measurement"""
        if not self.active:
            return
        
        if name not in self._runtimes:
            raise Exception("Runtime measurement %s was never started", name)

        duration = (time.time() - self._runtimes[name])
        event = {
            "type": "runtime",
            "time_ms": duration * 1000,
            "name": name
        }

        del self._runtimes[name]
        self.publish_event(event)

    def get_attributes(self):
        """Return a dict with all class attributes for monitoring"""
        attributes = {}

        if not self.active:
            return attributes
        
        # Find valid attributes to monitor
        for attr, v in self.__dict__.items():
            if attr in self._blacklist or callable(v):
                continue

            # Whitelist
            if self._whitelist is not None and attr not in self._whitelist:
                continue

            attributes[attr] = v

        return attributes

    def whitelist_attributes(self, whitelist:list|None, overwrite:bool=False):
        """Add or overwrite the whitelistet attributes. Set `whitelist` to None to deactivate the whitelist.
        To define the default value type use a dict `{name: ATTR_NAME, value_type: TYPE, unit: UNIT}` or tuple with (NAME, VALUE_TYPE)"""
        if not self.active:
            return self
        
        # Deactivate whitelist
        if whitelist is None:
            self._whitelist = None
            return self

        # Overwrite/activate whitelist
        if self._whitelist is None or overwrite:
            self._whitelist = []

        # No special arguments
        if all([isinstance(e, str) for e in whitelist]):
            self._whitelist.extend(whitelist)
            return self

        # Parse additional arguments
        for e in whitelist:
            if isinstance(e, dict):
                if not "name" in e:
                    raise Exception("Missing required key 'name' for whitelisting attribute! ", e)

                n = e["name"]

                # Whitelist
                self._whitelist.append(n)

                # Set attribute data
                self._attribute_data[n] = {
                    "value_type": None,
                    "unit": None
                }

                for key in ["value_type", "unit"]:
                    if key not in e:
                        continue

                    self._attribute_data[n][key] = e[key]

                continue
            elif isinstance(e, tuple):
                self._whitelist.append(e[0])

                self._attribute_data[e[0]] = {
                    "value_type": e[1],
                    "unit": None
                }
                continue

            self._whitelist.append(e)

        return self

    def blacklist_attributes(self, blacklist:list):
        """Add attributes to the blacklist so they will no longer be monitored"""
        if not self.active:
            return self
        
        self._blacklist.extend(blacklist)

    def set_attribute_type(self, attr_name:str, value_type:str|None):
        """Set the default value type of a attribute for the front-end. Will only be applied if the setting is done before the registration"""
        if not self.active:
            return self
        
        self._attribute_data[attr_name]["value_type"] = value_type
        return self

    def set_attribute_unit(self, attr_name:str, unit:str|None):
        """Set the unit of a attribute for the front-end. Will only be applied if the setting is done before the registration"""
        if not self.active:
            return self
        
        self._attribute_data[attr_name]["unit"] = unit
        return self

    def get_attribute_data(self, attr_name:str):
        """Return the attribute data entry if present otherwise return the default values"""
        if attr_name not in self._attribute_data:
            return {"value_type": None,
                    "unit": None}
        
        return self._attribute_data[attr_name]

    def publish_event(self, event:dict):
        """Publish a monitor event. (Overwrite for unit tests)"""
        if not Monitorable.active or not self.active:
            return
        
        if Monitorable.experiment_id is None:
            raise Exception("experiment_id of this class must be set")

        event.update({
            "obj_id": id(self),
            #"class_name": str(type(self).__name__),
            #"module": str(self.__class__.__module__)
        })
        
        #print("Monitor Event published:", event)
        logging.getLogger("monitor_logger").debug("Monitor published event: %s %s %s", str(self), event, id(self))
        publish("reconf_monitor_event_exchange", Monitorable.experiment_id, json.dumps(event))

class MonitorableABC(Monitorable, metaclass=ABCMeta):
    __slots__ = ()

    def __init__(self, no_monitoring=False):
        super().__init__(no_monitoring=no_monitoring)