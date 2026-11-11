import threading
import time
import json

from tools.rabbitmq_common_tools import publish

class SendingQueue():
    """Queues and sends queded messages in fixed time intervals"""

    # Problem: A client might get the inital data before the events are send, leading to duplicates (need detection in front-end)

    def __init__(self, target_queue:str, interval:float=1.0, msg_combine=None):
        self.target_queue = target_queue
        self.interval = interval
        self.msg_combine = msg_combine

        self.running = False
        self._thread = None
        self._buffer_lock = threading.Lock()
        self._buffer = []

    def add_msg(self, msg):
        """Add msg to queue"""
        with self._buffer_lock:
            self._buffer.append(msg)

    def start(self):
        """Start the sending process"""
        if self.running:
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._send_and_wait, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the sending thread"""
        if not self.running:
            return

        self.running = False
        self._thread.join()

    def _send_and_wait(self):
        while self.running:
            time.sleep(self.interval)

            # Second running check after sleep
            if not self.running:
                return

            with self._buffer_lock:
                if len(self._buffer) == 0:
                    continue

                # No combine method specified
                if self.msg_combine is None:
                    for msg in self._buffer:
                        publish("", self.target_queue, json.dumps(msg))

                    self._buffer.clear()
                    print("Send without combine")
                    continue

                # Combine msgs and send
                publish("", self.target_queue, json.dumps(self.msg_combine(self._buffer)))
                self._buffer.clear()
                print("Queue send messages")