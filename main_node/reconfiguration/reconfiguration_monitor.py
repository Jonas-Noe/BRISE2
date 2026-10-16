import os
import json

from tools.singleton import Singleton
from configuration_selection.configuration_selection import ConfigurationSelection

from tools.rabbitmq_common_tools import RabbitMQConnection

from reconfiguration.monitorable import Monitorable

class ReconfigurationMonitor(metaclass=Singleton):

    def __init__(self, cs:ConfigurationSelection):
        self.cs = cs

        # Activate monitors
        Monitorable.active = True

        if os.environ.get('TEST_MODE') != 'UNIT_TEST':
            self.connection_thread = self._EventServiceConnection(self, cs.experiment.unique_id)
            self.connection_thread.start()

    def on_event(self, ch, method, properties, body):
        event = json.loads(body.decode())

        #print("Monitor event:", event)

        if "type" not in event:
            print(f"RECONF MONITOR: {event['attr']} changed to {event['value']}")
            return

        if event["type"] == "func_runtime":
            print("MONITOR:", event["func_name"], "of", event["object"], "took", event["time_ms"], "ms")

    class _EventServiceConnection(RabbitMQConnection):
        """
        This class is responsible for listening to X queues.
        1. `stop_components` for shutting down configuration selection module (in case of BRISE Experiment termination).
        """

        def __init__(self, monitor_module, experiement_id):
            """
            The function for initializing consumer thread
            """
            self.monitor_module: ReconfigurationMonitor = monitor_module
            self.experiment_id = experiement_id
            super().__init__(monitor_module)

        def bind_and_consume(self):
            self.termination_result = self.channel.queue_declare(queue='', exclusive=True)
            self.termination_queue_name = self.termination_result.method.queue
            self.channel.queue_bind(exchange='experiment_termination_exchange',
                                    queue=self.termination_queue_name,
                                    routing_key=self.experiment_id)

            self.channel.basic_consume(queue="reconf_monitor_events" + self.experiment_id, auto_ack=True,
                                        on_message_callback=self.monitor_module.on_event)
            self.channel.basic_consume(queue=self.termination_queue_name, auto_ack=True,
                                        on_message_callback=self.stop)
    
