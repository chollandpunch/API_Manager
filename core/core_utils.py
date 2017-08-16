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



