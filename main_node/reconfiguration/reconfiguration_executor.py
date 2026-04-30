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
                return
            
            self.effectors[vp] = [effector]

    def change(self, variability_point:str, new_description:tuple, full_description:tuple):
        """Change the component for the given variability point according to the ``new_description``"""
        if variability_point not in self.effectors:
            raise KeyError("No effector for the variability point " + variability_point + " found!")
        
        for o in self.effectors[variability_point]:
            o.change(full_description if o.need_full_description else new_description)