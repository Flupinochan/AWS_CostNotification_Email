"""
▼Title
    Class for Logging
▼Author
    Flupinochan
▼Version
    1.0
▼Execution Environment
    Python 3.10 / For Lambda
▼Overview
    Class for logging
▼Remarks
    None
"""

import logging
import sys

from time import struct_time
from datetime import datetime
from logging import Formatter, StreamHandler
from zoneinfo import ZoneInfo



class LoggingClass:

    # ----------------------------------------------------------------------
    # Constant definition (class variables)
    # ----------------------------------------------------------------------

    # Log format
    LOG_FORMAT = '[%(asctime)s.%(msecs)03d JST] [%(levelname)s] [line %(lineno)d] [Function name : %(funcName)s] %(message)s'

    # %(asctime)s format
    LOG_DATEFMT = '%Y/%m/%d %H:%M:%S'

    # Time zone JST
    JST = ZoneInfo("Asia/Tokyo")

    # Log level (default is INFO)
    LOG_LEVEL = 'INFO'



    # ----------------------------------------------------------------------
    # Logger setting
    # ----------------------------------------------------------------------

    # Constructor
    def __init__(self, log_level='INFO'):
        self.LOG_LEVEL = log_level

        # Function for fmt.converter (required to set the timestamp of the log to JST)
        def custom_time(*args) -> struct_time:
            return datetime.now(self.JST).timetuple()

        # Define the log format
        fmt = Formatter(fmt=self.LOG_FORMAT, datefmt=self.LOG_DATEFMT)
        fmt.converter = custom_time

        # Define the log output destination
        sh = StreamHandler(sys.stdout)
        sh.setLevel(self.LOG_LEVEL)
        sh.setFormatter(fmt)

        # Create Logger object
        self.log = logging.getLogger('Logger_stdout')   # Instance variable
        self.log.propagate = False
        self.log.addHandler(sh)
        self.log.setLevel(self.LOG_LEVEL)



    # Function to get Logger object
    def get_logger(self):
        return self.log