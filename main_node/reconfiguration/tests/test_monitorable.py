import pytest

from reconfiguration.monitorable import Monitorable

class TestMonitorable:

    class TestObj(Monitorable):
        def __init__(self):
            self.name = "John"
            self.age = 20

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

    @pytest.fixture
    def monitored_object(self):
        o = self.TestObj()
        self._hook_publish_events(o)

        Monitorable.experiment_id = ""
        Monitorable.active = True

        return o

    def test_monitorable_activation(self, monitored_object:TestObj):
        """Test that the active value deactiveates the monitorable objects"""
        Monitorable.active = False
        monitored_object.change()

        assert_event({"attr": "name", "value": "Marry"}, monitored_object, not_send=True)

    def test_experiement_set_check(self):
        """Test that an exception is raised if the experiement is not set"""
        t = self.TestObj()
        Monitorable.active = True

        with pytest.raises(Exception):
            t.change()

    def test_attribute_monitoring(self, monitored_object:TestObj):
        "Test that class attribute changes are detected"
        monitored_object.change()

        assert_event({"attr": "name", "value": "Marry"}, monitored_object)
        assert_event({"attr": "age", "value": 22}, monitored_object)

    def test_monitor_runtime_monitoring(self, monitored_object:TestObj):
        """Test the different runtime monitoring options"""
        # Test method with decorator
        monitored_object.runtime_monitored_method()

        assert_event({
            "type": "func_runtime",
            "func_name": "runtime_monitored_method",
            "object": str(monitored_object)
        }, monitored_object)

        # Test partly
        monitored_object.partly_monitored_method()
        assert_event({
            "type": "runtime",
            "name": "partly",
            "object": str(monitored_object)
        }, monitored_object)

    def _hook_publish_events(self, monitorable:Monitorable):
        """Changes the `publish_event` method to just saveing the events for later checking."""
        monitorable.send_events = []
        monitorable.publish_event = lambda event, monitorable=monitorable:\
            monitorable.send_events.append(event)

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