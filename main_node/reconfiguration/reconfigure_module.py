from reconfiguration.reconfiguration_executor import ReconfigurationExecutor

from core_entities.experiment import Experiment
from configuration_selection.configuration_selection import ConfigurationSelection

from enum import Enum
from copy import deepcopy


class State(Enum):
    IDLE = 0 # No configuration requested or ongoing
    CONFIG_UNFINISHED = 1 # Reconfiguration requested but not all data received (waiting for .reconfigure())
    CONFIG_FINISHED = 2 # All reconfiguration data received

    # Might not be necessary
    CONFIGURING = 3 # Currenlty performing reconfiguration of components

class ReconfigureModule():

    """Handle (re)configuration of all components"""
    def __init__(self, experiment:Experiment, configuration_selection:ConfigurationSelection):
        self.state = State.IDLE

        self.experiment = experiment
        self.configuration_selection = configuration_selection

        # Current feature selection
        self._new_experiment_description = deepcopy(experiment.description)

        self._requested_changes = {}

        # Create the singleton executor to allow for observer registration
        self.executor = ReconfigurationExecutor()
        print(self.executor.orchestrators)

    #def init(self, experiment:Experiment, configuration_selection:ConfigurationSelection):
    #    """Allows to delay the initilization to make sure orchestrators are able to register"""
    #    self.experiment = experiment
    #    self.configuration_selection = configuration_selection

        # Current feature selection
    #    self._new_experiment_description = deepcopy(experiment.description)
    #    print(self.executor.orchestrators)

    ### Outline
    # Provide Methods for every needed variability point to change/re-init the component
    # Create a dict with the variability point names (e.g. SamplingStrategy) as keys and the corresponding re-init functions as values
    # Idea: Infer the correct function to use via variability point name? (--> using reflection)
    #   Like Naming change_* (e.g. sampling_strategy) and use this function, giving it the new feature data
    # Idea: Using vars() to find the created classes and replace them? Probably to many errors with regards to other initialization stuff
    #   Or it ends up to be different for every VP as well, because on how it needs to be changed

    # Annotations
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
        
        print("Found in current feature selection:", prev_feature_data)

        # Update the feature selection
        self._update_feature_selection(prev_feature_data["keys"], prev_feature_data["variability_point"], new_feature)
        #print("New feature selection", self._new_experiment_description)

        self._requested_changes[prev_feature["variability_point"]] = new_feature

    def reconfigure(self):
        """Signal that all reconfiguration requests are done. Set state to CONFIG_FINISHED"""
        assert self.state == State.CONFIG_UNFINISHED, "No configuration requested"

        # Perform reconfigure plan/requests
        for vp, new_feature in self._requested_changes.items():
            self.executor.change_component(vp, new_feature)

        self.state = State.CONFIG_FINISHED

    def _get_feature_data(self, feature_name_or_type:str)->dict:
        """Return a dict with the key ``parent`` specifing the variability point and the ``data`` with the
        configuration data of the feature."""
        return self._get_dict_key(feature_name_or_type, self._new_experiment_description)

    def _update_feature_selection(self, keys:list, parent_key:str, new_value):
        level = self._new_experiment_description
        keys.remove(parent_key)
        for key in keys:
            level = level[key]
        
        level[parent_key] = new_value

    def _get_dict_key(self, feature_name_or_type:str, dictionary:dict, parent_key:str="root", keys:list=[]) -> dict:
        """Return the dictornary with the given key, if it exists in a nested dict. Otherwise return a empty dict"""
        if feature_name_or_type in dictionary:
            return {"variability_point": parent_key, "parent": dictionary,
                    "data": dictionary[feature_name_or_type], "keys": keys}
        
        for key, value in dictionary.items():
            if isinstance(value, dict):
                result = self._get_dict_key(feature_name_or_type, value, key, keys)
                if result is not None:
                    keys.insert(0, key)
                    return result
                
                # Found by type
                if "Type" in value and value["Type"] == feature_name_or_type:
                    return {"variability_point": parent_key, "parent": dictionary,
                            "data": value, "keys": keys}
        
        return None
    
    