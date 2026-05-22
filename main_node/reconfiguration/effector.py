from typing import TypeVar, Generic

T = TypeVar("T")

class Effector(Generic[T]):

    instances = []

    # Create Component and Value Effector?
    # ValueEff need a var name
    # Component Effector takes in the reference? Would that work when upper component is replaced?

    def __init__(self, variability_point:str, description, *args, creation_method=None, need_full_description:bool=False, identifiers:None|list=None):
        self.variability_point = variability_point
        self.need_full_description = need_full_description
        self.identifiers = identifiers

        # Internal component that is object of change
        self._current_component = None

        # Use provided creation method (use to not inhert from this class)
        if creation_method is not None:
            self._create_component = creation_method

        # Create currently active component from scratch
        self.set(description, *args)

        Effector.instances.append(self)

    def __delete__(self, instance):
        print("Deleted effector", instance.variability_point, instance.get())
        Effector.instances.remove(instance)
    
    def set(self, description, *args):
        self._current_component = self._create_component(description, *args)
        self._args = args

    def change(self, description):
        """Change the stored component"""
        assert self._current_component is not None, "Effector is not initialized yet!"
        self._current_component = self._create_component(description, *self._args)

    def get(self) -> T:
        """Return the currently used component for this variability point"""
        return self._current_component
    
    def _create_component(self, description, *args) -> T:
        raise NotImplementedError("The method _create_component needs to be implemented!")
    
    def __str__(self):
        return self.variability_point + " " + str(self.identifiers)
    
    @classmethod
    def get_all_instances(cls):
        return cls.instances