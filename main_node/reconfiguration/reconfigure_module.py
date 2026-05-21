from reconfiguration.reconfiguration_executor import ReconfigurationExecutor

from core_entities.experiment import Experiment
from configuration_selection.configuration_selection import ConfigurationSelection

from enum import Enum
from copy import deepcopy

class State(Enum):
    IDLE = 0 # No configuration requested or ongoing
    CONFIG_UNFINISHED = 1 # Reconfiguration requested but not all data received (waiting for .reconfigure())
    CONFIG_FINISHED = 2 # All reconfiguration data received

class ReconfigureModule():
    """Handle reconfiguration of all components"""

    def __init__(self, experiment:Experiment, configuration_selection:ConfigurationSelection):
        self.state = State.IDLE

        self.experiment = experiment
        self.configuration_selection = configuration_selection

        # Current feature selection
        self._new_experiment_description = deepcopy(experiment.description)

        # Stores requested changes that will be performed by the executor
        self._requested_changes = {}

        self.executor = ReconfigurationExecutor()

    ### Annotations ###
    def configure_method(func):
        """Assert that configuring is allowed. Sets the state to CONFIG_UNFINISHED"""
        def inner(self, *args, **kwargs):
            assert self.state == State.IDLE or self.state == State.CONFIG_UNFINISHED,\
                "Configuring not allowed in state " + self.state.name
            
            result = func(self, *args, **kwargs)
            self.state = State.CONFIG_UNFINISHED
            return result
        return inner

    @configure_method
    def change_feature(self, prev_feature:str, new_feature:dict):
        """Request to change the ``prev_feature`` to a new feature"""
        # Select prev_feature by Type or Key in feature model or both?
        prev_feature_data = self._get_feature_data(prev_feature)
        if prev_feature_data is None:
            raise ValueError("prev_feature \"" + prev_feature + "\" was not found in current feature selection!")

        print("Change requested:", prev_feature)
        print("Prev feature: ", prev_feature_data)

        # Update the feature selection
        self._update_feature_selection(prev_feature_data["keys"], prev_feature_data["variability_point"], new_feature)
        print("New feature selection", self._new_experiment_description)

        # Need more percise way to address certain features (like Optimizer in Model_2 for example!)
        self._requested_changes[prev_feature_data["variability_point"]] = new_feature

    @configure_method
    def change_variant(self, variability_point:str, new_feature:dict, parent_nodes:None|list=None):
        """Request to change the given variability point to a new feature"""
        # Select prev_feature by Type or Key in feature model or both?
        parent_keys_list = self._get_variability_point_keys(variability_point, parent_nodes)
        if len(parent_keys_list) == 0:
            raise ValueError("Variability point " + variability_point + " was not found in the feature selection!")
        
        # Update the feature selection
        for parent_keys in parent_keys_list:
            self._update_feature_selection(parent_keys, variability_point, new_feature)
        #print("New feature selection", self._new_experiment_description)

        self._requested_changes[variability_point] = {"description": new_feature, "identifiers": parent_nodes}

        return self

    def done(self):
        """Signal that all reconfiguration requests are done. Set state to CONFIG_FINISHED"""
        assert self.state == State.CONFIG_UNFINISHED, "No configuration requested"
        self.state = State.CONFIG_FINISHED
        return self

    def reconfigure(self):
        """Performs the reconfiguration"""
        assert self.state == State.CONFIG_FINISHED, "No configuration requested or configuration is unfinished"

        # Perform reconfigure plan/requests
        for vp, changes in self._requested_changes.items():
            self.executor.change(vp, changes["description"], self._new_experiment_description, changes["identifiers"])

        self.state = State.IDLE

    def _get_variability_point_keys(self, vp:str, required_parent_nodes:None|list) -> list:
        """Returns a list of lists with parent keys for the variability point. All vps must have the given parent nodes. Otherwise they will be ignored"""
        paths = [k.split(" ") for k in self._flatten_keys(self._new_experiment_description, vp)]
        if required_parent_nodes is None or len(required_parent_nodes) == 0:
            return paths
        
        return [p for p in paths if set(p[-len(required_parent_nodes)-1:-1]) == set(required_parent_nodes)]
    
    def _flatten_keys(self, d:dict, search:str, parent_key=""):
        """Returns a list of strings with the flattend keys that end with the given search term. Single keys are separated by white spaces"""
        keys = []

        for key, value in d.items():
            new_key = parent_key + " " + key if parent_key else key
            if key == search:
                keys.append(new_key)
                return keys

            if isinstance(value, dict):
                keys.extend(self._flatten_keys(value, search, parent_key=new_key))
                continue

        return keys

    def _update_feature_selection(self, keys:list, parent_key:str, new_value):
        """Update the `_new_experiment_description`"""
        level = self._new_experiment_description
        keys.remove(parent_key)
        for key in keys:
            level = level[key]
        
        level[parent_key] = new_value

    def _update_feature_selection_values(self, keys:list, parent_key:str, new_values:dict):
        """Update all given values in the `_new_experiment_description` for the given path of keys"""
        level = self._new_experiment_description
        keys.remove(parent_key)
        for key in keys:
            level = level[key]
        
        for key, value in new_values.items():
            level[parent_key][key] = value
    
    