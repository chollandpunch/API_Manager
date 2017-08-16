"""Core utility library."""

from __future__ import with_statement

import six
import functools
import inspect
import os
import sys
import types
import logging
import threading





def pad_string(string):
  """Pad a string for safe HTTP error responses.
  Prevents Internet Explorer from displaying their own error messages
  when sent as the content of error responses.
  Args:
    string: A string.
  Returns:
    Formatted string left justified within a 512 byte field.
  """
  return string.ljust(512)


def positional(max_positional_args):
  """A decorator to declare that only the first N arguments may be positional.
  This decorator makes it easy to support Python 3 style keyword-only
  parameters. For example, in Python 3 it is possible to write:
    def fn(pos1, *, kwonly1=None, kwonly1=None):
      ...
  All named parameters after * must be a keyword:
    fn(10, 'kw1', 'kw2')  # Raises exception.
    fn(10, kwonly1='kw1')  # Ok.
  Example:
    To define a function like above, do:
      @positional(1)
      def fn(pos1, kwonly1=None, kwonly2=None):
        ...
    If no default value is provided to a keyword argument, it becomes a required
    keyword argument:
      @positional(0)
      def fn(required_kw):
        ...
    This must be called with the keyword parameter:
      fn()  # Raises exception.
      fn(10)  # Raises exception.
      fn(required_kw=10)  # Ok.
    When defining instance or class methods always remember to account for
    'self' and 'cls':
      class MyClass(object):
        @positional(2)
        def my_method(self, pos1, kwonly1=None):
          ...
        @classmethod
        @positional(2)
        def my_method(cls, pos1, kwonly1=None):
          ...
    One can omit the argument to 'positional' altogether, and then no
    arguments with default values may be passed positionally. This
    would be equivalent to placing a '*' before the first argument
    with a default value in Python 3. If there are no arguments with
    default values, and no argument is given to 'positional', an error
    is raised.
      @positional
      def fn(arg1, arg2, required_kw1=None, required_kw2=0):
        ...
      fn(1, 3, 5)  # Raises exception.
      fn(1, 3)  # Ok.
      fn(1, 3, required_kw1=5)  # Ok.
  Args:
    max_positional_arguments: Maximum number of positional arguments.  All
      parameters after the this index must be keyword only.
  Returns:
    A decorator that prevents using arguments after max_positional_args from
    being used as positional parameters.
  Raises:
    TypeError if a keyword-only argument is provided as a positional parameter.
    ValueError if no maximum number of arguments is provided and the function
      has no arguments with default values.
  """
  def positional_decorator(wrapped):
    @functools.wraps(wrapped)
    def positional_wrapper(*args, **kwargs):
      if len(args) > max_positional_args:
        plural_s = ''
        if max_positional_args != 1:
          plural_s = 's'
        raise TypeError('%s() takes at most %d positional argument%s '
                        '(%d given)' % (wrapped.__name__,
                                        max_positional_args,
                                        plural_s, len(args)))
      return wrapped(*args, **kwargs)
    return positional_wrapper

  if isinstance(max_positional_args, six.integer_types):
    return positional_decorator
  else:
    args, _, _, defaults = inspect.getargspec(max_positional_args)
    if defaults is None:
      raise ValueError(
          'Functions with no keyword arguments must specify '
          'max_positional_args')
    return positional(len(args) - len(defaults))(max_positional_args)


@positional(1)
def get_package_for_module(module):
  """Get package name for a module.
  Helper calculates the package name of a module.
  Args:
    module: Module to get name for.  If module is a string, try to find
      module in sys.modules.
  Returns:
    If module contains 'package' attribute, uses that as package name.
    Else, if module is not the '__main__' module, the module __name__.
    Else, the base name of the module file name.  Else None.
  """
  if isinstance(module, six.string_types):
    try:
      module = sys.modules[module]
    except KeyError:
      return None

  try:
    return six.text_type(module.package)
  except AttributeError:
    if module.__name__ == '__main__':
      try:
        file_name = module.__file__
      except AttributeError:
        pass
      else:
        base_name = os.path.basename(file_name)
        split_name = os.path.splitext(base_name)
        if len(split_name) == 1:
          return six.text_type(base_name)
        else:
          return u'.'.join(split_name[:-1])

    return six.text_type(module.__name__)

def wrapping(wrapped):
  # A decorator to decorate a decorator's wrapper.  Following the lead
  # of Twisted and Monocle, this is supposed to make debugging heavily
  # decorated code easier.  We'll see...
  # following the patch in http://bugs.python.org/issue3445. We can replace
  # this once upgrading to python 3.3.
  def wrapping_wrapper(wrapper):
    try:
      wrapper.__wrapped__ = wrapped
      wrapper.__name__ = wrapped.__name__
      wrapper.__doc__ = wrapped.__doc__
      wrapper.__dict__.update(wrapped.__dict__)
      # Local functions won't have __module__ attribute.
      if hasattr(wrapped, '__module__'):
        wrapper.__module__ = wrapped.__module__
    except Exception:
      pass
    return wrapper
  return wrapping_wrapper


def decorator(wrapped_decorator):
  """Converts a function into a decorator that optionally accepts keyword
  arguments in its declaration.

  Example usage:
    @utils.decorator
    def decorator(func, args, kwds, op1=None):
      ... apply op1 ...
      return func(*args, **kwds)

    # Form (1), vanilla
    @decorator
    foo(...)
      ...

    # Form (2), with options
    @decorator(op1=5)
    foo(...)
      ...

  Args:
    wrapped_decorator: A function that accepts positional args (func, args,
      kwds) and any additional supported keyword arguments.

  Returns:
    A decorator with an additional 'wrapped_decorator' property that is set to
  the original function.
  """
  def helper(_func=None, **options):
    def outer_wrapper(func):
      @wrapping(func)
      def inner_wrapper(*args, **kwds):
        return wrapped_decorator(func, args, kwds, **options)
      return inner_wrapper

    if _func is None:
      # Form (2), with options.
      return outer_wrapper

    # Form (1), vanilla.
    if options:
      # Don't allow @decorator(foo, op1=5).
      raise TypeError('positional arguments not supported')
    return outer_wrapper(_func)
  helper.wrapped_decorator = wrapped_decorator
  return helper


def build_mod_all_list(mod):
  if isinstance(mod, types.ModuleType):
    all = []
    for item in dir(mod):
      if isinstance(getattr(mod, item), (types.FunctionType, types.TypeType)):
        all.append(item)
    return all
  return None

def typename(obj):
  """Returns the type of obj as a string. More descriptive and specific than
  type(obj), and safe for any object, unlike __class__."""
  if hasattr(obj, '__class__'):
    return getattr(obj, '__class__').__name__
  else:
    return type(obj).__name__

def convertAllCaps(value):
  """Converts ALLCAPS_MESSAGE to Allcaps_Message"""
  return ''.join([x.upper() if (i==0 or (value[i-1]=='_' and i-1 >=0))
                  else x.lower() for i, x in enumerate(value)])

def createType(name, bases=(object,), dct={}, convert_case=True):
  name = convertAllCaps(name) if convert_case else name
  return type(name, bases, dct)
""" TEMP COMMENTED -- NOT NEEDED RIGHT AWAY ---"""
# import cgi
# __all__ = ['AcceptItem',
#            'AcceptError',
#            'Error',
#            'choose_content_type',
#            'decode_datetime',
#            'get_package_for_module',
#            'pad_string',
#            'parse_accept_header',
#            'positional',
#            'PROTORPC_PROJECT_URL',
#            'TimeZoneOffset',
#            'total_seconds',
# ]

# class AcceptError(Error):
#  """Raised when there is an error parsing the accept header."""

# PROTORPC_PROJECT_URL = 'http://code.google.com/p/google-protorpc'

#class AcceptItem(object):
  # """Encapsulate a single entry of an Accept header.
  # Parses and extracts relevent values from an Accept header and implements
  # a sort order based on the priority of each requested type as defined
  # here:
  #   http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html
  # Accept headers are normally a list of comma separated items.  Each item
  # has the format of a normal HTTP header.  For example:
  #   Accept: text/plain, text/html, text/*, */*
  # This header means to prefer plain text over HTML, HTML over any other
  # kind of text and text over any other kind of supported format.
  # This class does not attempt to parse the list of items from the Accept header.
  # The constructor expects the unparsed sub header and the index within the
  # Accept header that the fragment was found.
  # Properties:
  #   index: The index that this accept item was found in the Accept header.
  #   main_type: The main type of the content type.
  #   sub_type: The sub type of the content type.
  #   q: The q value extracted from the header as a float.  If there is no q
  #     value, defaults to 1.0.
  #   values: All header attributes parsed form the sub-header.
  #   sort_key: A tuple (no_main_type, no_sub_type, q, no_values, index):
  #       no_main_type: */* has the least priority.
  #       no_sub_type: Items with no sub-type have less priority.
  #       q: Items with lower q value have less priority.
  #       no_values: Items with no values have less priority.
  #       index: Index of item in accept header is the last priority.
  #"""

  #__CONTENT_TYPE_REGEX = re.compile(r'^([^/]+)/([^/]+)$')

  #def __init__(self, accept_header, index):
    # """Parse component of an Accept header.
    # Args:
    #   accept_header: Unparsed sub-expression of accept header.
    #   index: The index that this accept item was found in the Accept header.
    # """
    # accept_header = accept_header.lower()
    # content_type, values = cgi.parse_header(accept_header)
    # match = self.__CONTENT_TYPE_REGEX.match(content_type)
    # if not match:
    #   raise AcceptError('Not valid Accept header: %s' % accept_header)
    # self.__index = index
    # self.__main_type = match.group(1)
    # self.__sub_type = match.group(2)
    # self.__q = float(values.get('q', 1))
    # self.__values = values
    #
    # if self.__main_type == '*':
    #   self.__main_type = None
    #
    # if self.__sub_type == '*':
    #   self.__sub_type = None
    #
    # self.__sort_key = (not self.__main_type,
    #                    not self.__sub_type,
    #                    -self.__q,
    #                    not self.__values,
    #                    self.__index)

  # @property
  # def index(self):
  #   return self.__index
  #
  # @property
  # def main_type(self):
  #   return self.__main_type
  #
  # @property
  # def sub_type(self):
  #   return self.__sub_type
  #
  # @property
  # def q(self):
  #   return self.__q
  #
  # @property
  # def values(self):
  #   """Copy the dictionary of values parsed from the header fragment."""
  #   return dict(self.__values)
  #
  # @property
  # def sort_key(self):
  #   return self.__sort_key
  #
  # def match(self, content_type):
  #   """Determine if the given accept header matches content type.
  #   Args:
  #     content_type: Unparsed content type string.
  #   Returns:
  #     True if accept header matches content type, else False.
  #   """
  #   content_type, _ = cgi.parse_header(content_type)
  #   match = self.__CONTENT_TYPE_REGEX.match(content_type.lower())
  #   if not match:
  #     return False
  #
  #   main_type, sub_type = match.group(1), match.group(2)
  #   if not(main_type and sub_type):
  #     return False
  #
  #   return ((self.__main_type is None or self.__main_type == main_type) and
  #           (self.__sub_type is None or self.__sub_type == sub_type))
  #
  #
  # def __cmp__(self, other):
  #   """Comparison operator based on sort keys."""
  #   if not isinstance(other, AcceptItem):
  #     return NotImplemented
  #   return cmp(self.sort_key, other.sort_key)
  #
  # def __str__(self):
  #   """Rebuilds Accept header."""
  #   content_type = '%s/%s' % (self.__main_type or '*', self.__sub_type or '*')
  #   values = self.values
  #
  #   if values:
  #     value_strings = ['%s=%s' % (i, v) for i, v in values.items()]
  #     return '%s; %s' % (content_type, '; '.join(value_strings))
  #   else:
  #     return content_type
  #
  # def __repr__(self):
  #   return 'AcceptItem(%r, %d)' % (str(self), self.__index)

""" TEMP COMMENT - not needed right away"""
# def parse_accept_header(accept_header):
#   """Parse accept header.
#   Args:
#     accept_header: Unparsed accept header.  Does not include name of header.
#   Returns:
#     List of AcceptItem instances sorted according to their priority.
#   """
#   accept_items = []
#   for index, header in enumerate(accept_header.split(',')):
#     accept_items.append(AcceptItem(header, index))
#   return sorted(accept_items)

""" TEMP COMMENT - not needed right away"""
# def choose_content_type(accept_header, supported_types):
#   """Choose most appropriate supported type based on what client accepts.
#   Args:
#     accept_header: Unparsed accept header.  Does not include name of header.
#     supported_types: List of content-types supported by the server.  The index
#       of the supported types determines which supported type is prefered by
#       the server should the accept header match more than one at the same
#       priority.
#   Returns:
#     The preferred supported type if the accept header matches any, else None.
#   """
#   for accept_item in parse_accept_header(accept_header):
#     for supported_type in supported_types:
#       if accept_item.match(supported_type):
#         return supported_type
#   return None



