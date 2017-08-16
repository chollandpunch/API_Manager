"""Datetime utilities."""
import datetime as dt
import re

from core._system import constants

_TIME_ZONE_RE_STRING = r"""
  # Examples:
  #   +01:00
  #   -05:30
  #   Z12:00
  ((?P<z>Z) | (?P<sign>[-+])
   (?P<hours>\d\d) :
   (?P<minutes>\d\d))$
"""
_TIME_ZONE_RE = re.compile(_TIME_ZONE_RE_STRING, re.IGNORECASE | re.VERBOSE)

def now(utc=False):
  d = dt.datetime.now(tz=constants.LOCAL_TIMEZONE)
  if utc:
    return d.astimezone(constants.UTC_TIMEZONE)
  else:
    return d


def asDict(date_obj):
  tt = date_obj.timetuple()
  return {'yr': tt.tm_year,
          'mo': tt.tm_mon,
          'dy': tt.tm_mday,
          'hr': tt.tm_hour,
          'mi': tt.tm_min,
          'sc': tt.tm_sec,
          'DYint': tt.tm_wday,
          'YRDYint': tt.tm_yday,
          'isdst': tt.tm_isdst
          }


def convertToUTC(date_obj):
  tzinfo = date_obj.tzinfo
  if not tzinfo:
    #Assume local time.
    date_obj = date_obj.replace(tzinfo=constants.LOCAL_TIMEZONE)
  return date_obj.astimezone(constants.UTC_TIMEZONE)

def decode_datetime(encoded_datetime):
  """Decode a DateTimeField parameter from a string to a python datetime.
  Args:
    encoded_datetime: A string in RFC 3339 format.
  Returns:
    A datetime object with the date and time specified in encoded_datetime.
  Raises:
    ValueError: If the string is not in a recognized format.
  """
  # Check if the string includes a time zone offset.  Break out the
  # part that doesn't include time zone info.  Convert to uppercase
  # because all our comparisons should be case-insensitive.
  time_zone_match = _TIME_ZONE_RE.search(encoded_datetime)
  if time_zone_match:
    time_string = encoded_datetime[:time_zone_match.start(1)].upper()
  else:
    time_string = encoded_datetime.upper()

  if '.' in time_string:
    format_string = '%Y-%m-%dT%H:%M:%S.%f'
  else:
    format_string = '%Y-%m-%dT%H:%M:%S'

  decoded_datetime = dt.datetime.strptime(time_string, format_string)

  if not time_zone_match:
    return decoded_datetime

  # Time zone info was included in the parameter.  Add a tzinfo
  # object to the datetime.  Datetimes can't be changed after they're
  # created, so we'll need to create a new one.
  if time_zone_match.group('z'):
    offset_minutes = 0
  else:
    sign = time_zone_match.group('sign')
    hours, minutes = [int(value) for value in
                      time_zone_match.group('hours', 'minutes')]
    offset_minutes = hours * 60 + minutes
    if sign == '-':
      offset_minutes *= -1

  return dt.datetime(decoded_datetime.year,
                     decoded_datetime.month,
                     decoded_datetime.day,
                     decoded_datetime.hour,
                     decoded_datetime.minute,
                     decoded_datetime.second,
                     decoded_datetime.microsecond,
                     TimeZoneOffset(offset_minutes))

def total_seconds(offset):
  """Backport of offset.total_seconds() from python 2.7+."""
  seconds = offset.days * 24 * 60 * 60 + offset.seconds
  microseconds = seconds * 10**6 + offset.microseconds
  return microseconds / (10**6 * 1.0)


class TimeZoneOffset(dt.tzinfo):
  """Time zone information as encoded/decoded for DateTimeFields."""

  def __init__(self, offset):
    """Initialize a time zone offset.
    Args:
      offset: Integer or timedelta time zone offset, in minutes from UTC.  This
        can be negative.
    """
    super(TimeZoneOffset, self).__init__()
    if isinstance(offset, dt.timedelta):
      offset = total_seconds(offset) / 60
    self.__offset = offset

  def utcoffset(self, dt):
    """Get the a timedelta with the time zone's offset from UTC.
    Returns:
      The time zone offset from UTC, as a timedelta.
    """
    return dt.timedelta(minutes=self.__offset)

  def dst(self, dt):
    """Get the daylight savings time offset.
    The formats that ProtoRPC uses to encode/decode time zone information don't
    contain any information about daylight savings time.  So this always
    returns a timedelta of 0.
    Returns:
      A timedelta of 0.
    """
    return dt.timedelta(0)

def _date_to_datetime(value):
  """Convert a date to a datetime for Cloud Datastore storage.

  Args:
    value: A datetime.date object.

  Returns:
    A datetime object with time set to 0:00.
  """
  if not isinstance(value, dt.date):
    raise TypeError('Cannot convert to datetime expected date value; '
                    'received %s' % value)
  return dt.datetime(value.year, value.month, value.day)


def _time_to_datetime(value):
  """Convert a time to a datetime for Cloud Datastore storage.

  Args:
    value: A datetime.time object.

  Returns:
    A datetime object with date set to 1970-01-01.
  """
  if not isinstance(value, dt.time):
    raise TypeError('Cannot convert to datetime expected time value; '
                    'received %s' % value)
  return dt.datetime(1970, 1, 1,
                           value.hour, value.minute, value.second,
                           value.microsecond)









"""Below is unused decorator test"""

def forceUTC(func):
  """Decorator that converts any datetime object to UTC."""

  def wrapper(*args, **kwargs):
    args = list(args)
    for idx, arg in enumerate(args):
      if isinstance(arg, dt.datetime):
        args[idx] = convertToUTC(arg)
    for k, v in kwargs:
      if isinstance(v, dt.datetime):
        kwargs[k] = convertToUTC(v)
    return func(*args, **kwargs)
  return wrapper

@forceUTC
def test(non_date_str, date_obj, kw1=False, kw2='hi'):
  def NDS():
    return 'non_date_str: {0}'

  def DOS():
    return 'date_obj: {0}'

  print NDS().format(non_date_str)
  print DOS().format(date_obj)
  print kw1
  print kw2