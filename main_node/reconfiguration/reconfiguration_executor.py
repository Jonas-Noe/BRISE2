from reconfiguration.orchestrator import Orchestrator
from reconfiguration.effector import Effector

class ReconfigurationExecutor():

    def __init__(self):
        self.effectors = {}
        self._update_effectors()

    def _update_effectors(self):
        """Load all effectors in the `effectors`dict. Key is the variability point and the value is the instance of the effector"""
        self.effectors = {}

        for effector in Effector.get_all_instances():
            vp = effector.variability_point
            if vp in self.effectors:
                self.effectors[vp].append(effector)
                continue
            
            self.effectors[vp] = [effector]

    def change(self, variability_point:str, new_description:tuple, full_description:tuple, identifiers:None|list):
        """Change the component for the given variability point according to the ``new_description``"""
        if variability_point not in self.effectors:
            raise KeyError("No effector for the variability point " + variability_point + " found!")
        
        for o in self.effectors[variability_point]:
            if identifiers is not None and len(identifiers) != 0: # Allow all identifiers if none are specified
                if len(o.identifiers) == 0 or set(o.identifiers) != set(identifiers): # (all identifiers must match IF any identifiers are specified)
                    continue
            
            o.change(full_description if o.need_full_description else new_description)