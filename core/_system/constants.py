import datetime
import dateutil.tz as tz
import importlib

import os
import inspect
import sys

IMPORTER = importlib.import_module
CRITICALFAIL_MSG = ('CRITICAL FAILURE!!! MISSING SYSTEM.PY FILE IN "core.errors_old.err_msg"\n'
                    'Exiting...')
ROOT_PATH = os.path.abspath('.').replace('\\', '/')
ERROR_PATH = ROOT_PATH + '/errors_old'
DATA_PATH = ROOT_PATH + '/data'
LOG_PATH = DATA_PATH + '/logs'

LOCAL_TIMEZONE = tz.tzlocal()
UTC_TIMEZONE = tz.tzutc()
LOCAL_TIMEZONE_STR = datetime.datetime.now(tz.tzlocal()).tzname()

ERRORKEY_DEFAULTKEYS = ('basekey', 'localkey', 'msgkey')
ERRORKEY_SYSTEM_DEFAULTKEYS = ('System', 'Generic', 'Defaultmsg')