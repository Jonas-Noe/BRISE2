import json
import time
from tools.rabbitmq_common_tools import publish

class Monitorable:
    '''Monitors all changes in the object'''

    experiment_id = None
    active = False

    def __setattr__(self, name, value):
        '''Added default behavior to notify on value change. Does not affect lists, dicts, etc.'''
        if (hasattr(self, name) and getattr(self, name) != value):
            self._on_value_changed(name, value)
        else:
            #print(f"Unnoticed: {name} changed to {value}")
            pass

        super().__setattr__(name, value)

    def _on_value_changed(self, name, value):
        if not Monitorable.active:
            return

        print(f"Monitor: {name} changed to {value}")
        event = {"attr": name, "value": value}

        if Monitorable.experiment_id is None:
            raise UnboundLocalError("experiment_id of this class must be set")

        # Send the event to the monitor module
        publish("reconf_monitor_events", Monitorable.experiment_id, json.dumps(event))

    def monitor_runtime(name:str|None=None):
        """Decorator to register a function for runtime monitoring"""
        def monitor_runtime(func):
            def inner(self, *args, **kwargs):
                start = time.time()
                ret_val = func(self, *args, **kwargs)
                duration = time.time() - start

                if not Monitorable.active:
                    return ret_val

                event = {
                    "type": "func_runtime",
                    "func_name": func.__name__,
                    "time_ms": duration / 1000,
                    "name": name if name is not None else "",
                    "object": str(self)
                }

                publish("reconf_monitor_events", Monitorable.experiment_id, json.dumps(event))

                return ret_val
            return inner
        return monitor_runtime