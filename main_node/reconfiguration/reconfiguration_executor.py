from reconfiguration.orchestrator import Orchestrator

class ReconfigurationExecutor():

    def __init__(self):
        self.orchestrators = {}
        self._init_orchestrators()

    def _init_orchestrators(self):
        """Adds all created orchestrators into the ``orchestrator`` dict.
        Key is the variability point and the values is the orchestrator instance"""
        for orchestrator in Orchestrator.get_all_orchestrators():
            vp = orchestrator.variability_point
            if vp in self.orchestrators:
                self.orchestrators[vp].append(orchestrator)
                return
            
            self.orchestrators[vp] = [orchestrator]

    def change_component(self, variability_point:str, new_description:tuple):
        """Change the component for the given variability point according to the ``new_description``"""
        if variability_point not in self.orchestrators:
            raise KeyError("No orchestrators for the variability point " + variability_point + " found!")
        
        for o in self.orchestrators[variability_point]:
            o.change_component(new_description)