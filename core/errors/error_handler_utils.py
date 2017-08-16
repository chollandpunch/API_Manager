import collections
import copy
import json
import pprint

from core.utils import file_util
from core._system.constants import *
from core.errors.err_msg_utils import LocalKey, msgkey
from core import core_utils

def dictToInstance(_instance, _dict):
    # print '\n\nLoading:\n'
    # print _instance, '\n'
    # print _dict, '\n'
    """Transfers the key/value pairs from the dict and assigns them as 
    instance variables."""

    [setattr(_instance, k, v) for k, v in _dict.iteritems()]
    return _instance

def createBasicClass(name, bases=(object,), dct={}):
    cls = type(name, bases, dct)
    return cls

def _getErrmsgData(page):
    data_dict = {
        'description': page.__doc__ if page.__doc__ else '',
        'local_keys': [],
        'attributes': []
    }

    # Parse ErrMsg page
    for prop in [x for x in dir(page) if not x.startswith('_')]:
        prop_val, key = [core_utils.convertAllCaps(prop),
                         getattr(page, prop)], None  # Prop: (Name, Value)

        # Filter prop values
        if isinstance(prop_val[1], LocalKey):  # Interpret as a LocalKey Message
            key = 'local_keys'
            prop_val[0] = core_utils.convertAllCaps(prop_val[0])
        elif prop == prop.upper():  # Interpret as a BaseKey Property
            key = 'attributes'
            prop_val[0] = prop_val[0].lower()
        else:
            pass  # Ignore everything else

        if key:
            data_dict[key].append(prop_val)

    if 'location' not in data_dict.keys():
        data_dict['location'] = '(Not Available)'

    return data_dict

def _check_LocalKeyDefault(base_obj, local_list):
    """Ensures a Default LocalKey is added to BaseKey objects."""

    if ERRORKEY_SYSTEM_DEFAULTKEYS[1] not in [x[0] for x in local_list]:
        default_msg = msgkey(ERRORKEY_SYSTEM_DEFAULTKEYS[2],
                             'General error in {0} object'.format(base_obj._comps[0]))
        local_msg = LocalKey(
            desc='Default LocalKey in {0} object'.format(base_obj._comps[0]),
            location=base_obj.location,
            messages=[default_msg]
        )
        local_list.append((ERRORKEY_SYSTEM_DEFAULTKEYS[1], local_msg))
        base_obj._keys.append(ERRORKEY_SYSTEM_DEFAULTKEYS[1])
    return local_list

def _check_MsgKeyDefault(local_obj, msg_list):
    """Ensures a Default MessageKey is added to LocalKey objects."""
    if ERRORKEY_SYSTEM_DEFAULTKEYS[2] not in [x.key for x in msg_list]:
        default_msg = msgkey(ERRORKEY_SYSTEM_DEFAULTKEYS[2],
                             'General error in {0} object'.format(
                                 core_utils.convertAllCaps(local_obj._comps[0])))
        msg_list.append(default_msg)
        local_obj._keys.append(ERRORKEY_SYSTEM_DEFAULTKEYS[2])
    return msg_list