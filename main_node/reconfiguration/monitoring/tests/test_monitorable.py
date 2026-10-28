import pytest

from reconfiguration.monitoring.monitorable import Monitorable

class TestMonitorable:

    class MonitorObj(Monitorable):
        def __init__(self):
            self.name = "John"
            self.age = 20

            super().__init__()

            self.send_events = []

        def change(self):
            self.name = "Marry"
            self.age = 22

        @Monitorable.monitor_runtime()
        def runtime_monitored_method(self):
            self.do_heavy_work()

        def do_heavy_work(self):
            for x in range(1000):
                y = x % 3

        def partly_monitored_method(self):
            self.start_runtime("partly")
            for x in range(1000):
                y = x + 1
            self.stop_runtime("partly")

            self.do_heavy_work()

        # Altered publish method for testing
        def publish_event(self, event):
            self.send_events.append(event)

    @pytest.fixture
    def monitored_object(self):
        o = self.MonitorObj()

        Monitorable.experiment_id = ""
        Monitorable.active = True

        return o

    def test_monitorable_activation(self, monitored_object:MonitorObj):
        """Test that the active value deactiveates the monitorable objects"""
        Monitorable.active = False
        monitored_object.change()

        assert_event({"attr": "name", "value": "Marry"}, monitored_object, not_send=True)

    def test_experiement_set_check(self):
        """Test that an exception is raised if the experiement is not set"""
        class Test(Monitorable):
            def __init__(self):
                super().__init__()

        t = Test()
        Monitorable.active = True
        
        with pytest.raises(Exception):
            t.change()

    def test_attribute_monitoring(self, monitored_object:MonitorObj):
        "Test that class attribute changes are detected"
        monitored_object.change()

        assert_event({"attr": "name", "value": "Marry"}, monitored_object)
        assert_event({"attr": "age", "value": 22}, monitored_object)

    def test_monitor_runtime_monitoring(self, monitored_object:MonitorObj):
        """Test the different runtime monitoring options"""
        # Test method with decorator
        monitored_object.runtime_monitored_method()

        assert_event({
            "type": "func_runtime",
            "func_name": "runtime_monitored_method",
        }, monitored_object)

        # Test partly
        monitored_object.partly_monitored_method()
        assert_event({
            "type": "runtime",
            "name": "partly",
        }, monitored_object)

    def test_instance_creation(self, monitored_object:MonitorObj):
        """Test that new instances call their init method and instances get saved"""
        class Test(Monitorable):
            def __init__(self):
                super().__init__()

        t = Test()

        assert t in Monitorable.instances # Assert instance was saved
        assert monitored_object in Monitorable.instances

    def test_get_attributes(self, monitored_object:MonitorObj):
        """Test the get_attributes method"""
        attributes = monitored_object.get_attributes()

        assert len(attributes.keys()) == 3 # 2 + 1 (for send_events)

        assert "name" in attributes
        assert "age" in attributes

        assert attributes["name"] == "John"
        assert attributes["age"] == 20

    def test_attribute_whitelist(self, monitored_object:MonitorObj):
        """Test that the whitelist function works correctly"""
        monitored_object.whitelist_attributes(["name"])

        monitored_object.change()

        assert_event({"type": "attribute_change", "attr": "name", "value": "Marry"}, monitored_object)
        assert_event({"type": "attribute_change", "attr": "age", "value": 22}, monitored_object, not_send=True)
        assert_event({"type": "attribute_change", "attr": "_whitelist", "value": ["name"]}, monitored_object, not_send=True)

        # Turn whitelist off
        monitored_object.whitelist_attributes(None)
        assert_event({"type": "attribute_change", "attr": "name", "value": "Marry"}, monitored_object)
        assert_event({"type": "attribute_change", "attr": "age", "value": 22}, monitored_object)

    def test_attribute_blacklist(self, monitored_object:MonitorObj):
        """Test that the blacklist function works correctly"""
        monitored_object.blacklist_attributes(["age"])

        monitored_object.change()

        assert_event({"type": "attribute_change", "attr": "name", "value": "Marry"}, monitored_object)
        assert_event({"type": "attribute_change", "attr": "age", "value": 22}, monitored_object, not_send=True)

def assert_event(event:dict, monitorable:Monitorable, not_send:bool=False):
    """Helper method to assert that a special event was send.
    Checks that alle keys that are present in `event`
    match with the send event keys and values.
    Set `not_send` to true for checking that no such event has been send."""
    if not hasattr(monitorable, "send_events"):
        raise Exception("Monitorable object is not hooked for event asserting")
    
    # Check that an event with all keys and values exist
    for e in monitorable.send_events:
        # Match found
        if event.items() <= e.items():
            if not_send:
                assert False, "Event not expected to be sent was send!"

            monitorable.send_events.remove(e)
            return

    if not_send:
        return
    
    assert False, "Expected event was not send!"