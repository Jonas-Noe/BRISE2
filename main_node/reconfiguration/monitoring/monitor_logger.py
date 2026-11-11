import logging

monitor_logger = None

def init():
    global monitor_logger
    monitor_logger = logging.getLogger("monitor_logger")
    monitor_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(fmt='%(asctime)s - %(levelname)-8s - %(threadName)s - %(filename)s:%(lineno)d |> %(message)s',
                                  datefmt='%d.%m.%Y %H:%M:%S')

    fh = logging.FileHandler("./monitor.log", mode="w")
    sh = logging.StreamHandler()

    fh.setFormatter(formatter)
    sh.setFormatter(formatter)

    monitor_logger.addHandler(fh)
    monitor_logger.addHandler(sh)

    