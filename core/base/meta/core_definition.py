import six

from core import core_constants as constants
from core import core_utils as util

__all__ = ['_DefinitionClass']

class _DefinitionClass(type):
  """Base meta-class used for definition meta-classes.
  The Enum and Message definition classes share some basic functionality.
  Both of these classes may be contained by a Message definition.  After
  initialization, neither class may have attributes changed
  except for the protected _message_definition attribute, and that attribute
  may change only once.
  """

  __initialized = False

  def __init__(cls, name, bases, dct):
    """Constructor."""
    type.__init__(cls, name, bases, dct)
    # Base classes may never be initialized.
    if cls.__bases__ != (object,):
      cls.__initialized = True

  def message_definition(cls):
    """Get outer Message definition that contains this definition.
    Returns:
      Containing Message definition if definition is contained within one,
      else None.
    """
    try:
      return cls._message_definition()
    except AttributeError:
      return None

  def __setattr__(cls, name, value):
    """Overridden so that cannot set variables on definition classes after init.
    Setting attributes on a class must work during the period of initialization
    to set the enumation value class variables and build the name/number maps.
    Once __init__ has set the __initialized flag to True prohibits setting any
    more values on the class.  The class is in effect frozen.
    Args:
      name: Name of value to set.
      value: Value to set.
    """
    if cls.__initialized and name not in constants._POST_INIT_ATTRIBUTE_NAMES:
      raise AttributeError('May not change values: %s' % name)
    else:
      type.__setattr__(cls, name, value)

  def __delattr__(cls, name):
    """Overridden so that cannot delete varaibles on definition classes."""
    raise TypeError('May not delete attributes on definition class')

  def definition_name(cls):
    """Helper method for creating definition name.
    Names will be generated to include the classes package name, scope (if the
    class is nested in another definition) and class name.
    By default, the package name for a definition is derived from its module
    name.  However, this value can be overriden by placing a 'package' attribute
    in the module that contains the definition class.  For example:
      package = 'some.alternate.package'
      class MyMessage(Message):
        ...
      >>> MyMessage.definition_name()
      some.alternate.package.MyMessage
    Returns:
      Dot-separated fully qualified name of definition.
    """
    outer_definition_name = cls.outer_definition_name()
    if outer_definition_name is None:
      return six.text_type(cls.__name__)
    else:
      return u'%s.%s' % (outer_definition_name, cls.__name__)

  def outer_definition_name(cls):
    """Helper method for creating outer definition name.
    Returns:
      If definition is nested, will return the outer definitions name, else the
      package name.
    """
    outer_definition = cls.message_definition()
    if not outer_definition:
      return util.get_package_for_module(cls.__module__)
    else:
      return outer_definition.definition_name()

  def definition_package(cls):
    """Helper method for creating creating the package of a definition.
    Returns:
      Name of package that definition belongs to.
    """
    outer_definition = cls.message_definition()
    if not outer_definition:
      return util.get_package_for_module(cls.__module__)
    else:
      return outer_definition.definition_package()