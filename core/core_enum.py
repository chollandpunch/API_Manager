"""Core Meta classes"""
import six

import core.core_constants as constants
import core.errors_old.core_error as error
import core.base.meta.core_definition as definition

__all__ = ['_EnumClass', 'Enum', 'Variant', 'defaultValue']

class _EnumClass(definition._DefinitionClass):
  """Meta-class used for defining the Enum base class.
  Meta-class enables very specific behavior for any defined Enum
  class.  All attributes defined on an Enum sub-class must be integers.
  Each attribute defined on an Enum sub-class is translated
  into an instance of that sub-class, with the name of the attribute
  as its name, and the number provided as its value.  It also ensures
  that only one level of Enum class hierarchy is possible.  In other
  words it is not possible to declare sub-classes of sub-classes of
  Enum.
  This class also defines some functions in order to restrict the
  behavior of the Enum class and its sub-classes.  It is not possible
  to change the behavior of the Enum class in later classes since
  any new classes may be defined with only integer values, and no methods.
  """

  def __init__(cls, name, bases, dct):
    # Can only define one level of sub-classes below Enum.
    if not (bases == (object,) or bases == (Enum,)):
      raise error.EnumDefinitionError('Enum type %s may only inherit from Enum' % (name,))

    cls.__by_number = {}
    cls.__by_name = {}

    # Enum base class does not need to be initialized or locked.
    if bases != (object,):
      # Replace integer with number.
      for attribute, value in dct.items():

        # Module will be in every enum class.
        if attribute in constants._RESERVED_ATTRIBUTE_NAMES:
          continue

        # Reject anything that is not an int.
        if not isinstance(value, six.integer_types):
          raise error.EnumDefinitionError(
              'May only use integers in Enum definitions.  Found: %s = %s' %
              (attribute, value))

        # Protocol buffer standard recommends non-negative values.
        # Reject negative values.
        if value < 0:
          raise error.EnumDefinitionError(
              'Must use non-negative enum values.  Found: %s = %d' %
              (attribute, value))

        if value > constants.MAX_ENUM_VALUE:
          raise error.EnumDefinitionError(
              'Must use enum values less than or equal %d.  Found: %s = %d' %
              (constants.MAX_ENUM_VALUE, attribute, value))

        if value in cls.__by_number:
          raise error.EnumDefinitionError(
              'Value for %s = %d is already defined: %s' %
              (attribute, value, cls.__by_number[value].name))

        # Create enum instance and list in new Enum type.
        instance = object.__new__(cls)
        # pylint:disable=non-parent-init-called
        cls.__init__(instance, attribute, value)
        cls.__by_name[instance.name] = instance
        cls.__by_number[instance.number] = instance
        setattr(cls, attribute, instance)

    if cls.__by_number:
      lowest = min(cls.__by_number.keys())
      instance = cls.lookup_by_number(lowest)
      setattr(cls, '_DEFAULT', instance)
    definition._DefinitionClass.__init__(cls, name, bases, dct)

  def __iter__(cls):
    """Iterate over all values of enum.
    Yields:
      Enumeration instances of the Enum class in arbitrary order.
    """
    return iter(cls.__by_number.values())

  def names(cls):
    """Get all names for Enum.
    Returns:
      An iterator for names of the enumeration in arbitrary order.
    """
    return cls.__by_name.keys()

  def numbers(cls):
    """Get all numbers for Enum.
    Returns:
      An iterator for all numbers of the enumeration in arbitrary order.
    """
    return cls.__by_number.keys()

  def lookup_by_name(cls, name):
    """Look up Enum by name.
    Args:
      name: Name of enum to find.
    Returns:
      Enum sub-class instance of that value.
    """
    return cls.__by_name[name]

  def lookup_by_number(cls, number):
    """Look up Enum by number.
    Args:
      number: Number of enum to find.
    Returns:
      Enum sub-class instance of that value.
    """
    return cls.__by_number[number]

  def set_default(self, name_or_number):
    """Set Default value for Enum. Can only change once."""
    cls = self.__class__
    if self._DEFAULT == cls.lookup_by_number(self, min(cls.numbers(self))):
      if isinstance(name_or_number, int):
        if name_or_number in cls.numbers(self):
          self._DEFAULT = cls.lookup_by_number(self, name_or_number)
        else:
          raise TypeError('No such value for %s in Enum %s' %
                          (name_or_number, cls.__name__))
      else:
        if name_or_number in cls.names(self):
          self._DEFAULT = cls.lookup_by_name(self, name_or_number)
        else:
          raise TypeError('No such name for %s in Enum %s' %
                          (name_or_number, cls.__name__))
    else:
      raise AttributeError('%s._DEFAULT is locked.' % self.__name__)

  def __len__(cls):
    return len(cls.__by_name)


class Enum(object):
  """Base class for all enumerated types."""

  __metaclass__ = _EnumClass
  __slots__ = set(('name', 'number'))

  def __new__(cls, index):
    """Acts as look-up routine after class is initialized.
    The purpose of overriding __new__ is to provide a way to treat
    Enum subclasses as casting types, similar to how the int type
    functions.  A program can pass a string or an integer and this
    method with "convert" that value in to an appropriate Enum instance.
    Args:
      index: Name or number to look up.  During initialization
        this is always the name of the new enum value.
    Raises:
      TypeError: When an inappropriate index value is passed provided.
    """
    # If is enum type of this class, return it.
    if isinstance(index, cls):
      return index

    # If number, look up by number.
    if isinstance(index, six.integer_types):
      try:
        return cls.lookup_by_number(index)
      except KeyError:
        pass

    # If name, look up by name.
    if isinstance(index, six.string_types):
      try:
        return cls.lookup_by_name(index)
      except KeyError:
        pass

    raise TypeError('No such value for %s in Enum %s' %
                    (index, cls.__name__))

  def __init__(self, name, number=None):
    """Initialize new Enum instance.
    Since this should only be called during class initialization any
    calls that happen after the class is frozen raises an exception.
    """
    # Immediately return if __init__ was called after _Enum.__init__().
    # It means that casting operator version of the class constructor
    # is being used.
    if getattr(type(self), '_DefinitionClass__initialized'):
      return
    object.__setattr__(self, 'name', name)
    object.__setattr__(self, 'number', number)


  def __setattr__(self, name, value):
    raise TypeError('May not change enum values')

  def __str__(self):
    return self.name

  def __int__(self):
    return self.number

  def __repr__(self):
    return '%s(%s, %d)' % (type(self).__name__, self.name, self.number)

  def __reduce__(self):
    """Enable pickling.
    Returns:
      A 2-tuple containing the class and __new__ args to be used for restoring
      a pickled instance.
    """
    return self.__class__, (self.number,)

  def __cmp__(self, other):
    """Order is by number."""
    if isinstance(other, type(self)):
      return cmp(self.number, other.number)
    return NotImplemented

  def __lt__(self, other):
    """Order is by number."""
    if isinstance(other, type(self)):
      return self.number < other.number
    return NotImplemented

  def __le__(self, other):
    """Order is by number."""
    if isinstance(other, type(self)):
      return self.number <= other.number
    return NotImplemented

  def __eq__(self, other):
    """Order is by number."""
    if isinstance(other, type(self)):
      return self.number == other.number
    return NotImplemented

  def __ne__(self, other):
    """Order is by number."""
    if isinstance(other, type(self)):
      return self.number != other.number
    return NotImplemented

  def __ge__(self, other):
    """Order is by number."""
    if isinstance(other, type(self)):
      return self.number >= other.number
    return NotImplemented

  def __gt__(self, other):
    """Order is by number."""
    if isinstance(other, type(self)):
      return self.number > other.number
    return NotImplemented

  def __hash__(self):
    """Hash by number."""
    return hash(self.number)

  @classmethod
  def to_dict(cls):
    """Make dictionary version of enumerated class.
    Dictionary created this way can be used with def_num.
    Returns:
      A dict (name) -> number
    """
    return dict((item.name, item.number) for item in iter(cls))

  @staticmethod
  def def_enum(dct, name):
    """Define enum class from dictionary.
    Args:
      dct: Dictionary of enumerated values for type.
      name: Name of enum.
    """
    return type(name, (Enum,), dct)


class Variant(Enum):
  """Wire format variant.

  Values:
    DOUBLE: 64-bit floating point number.
    FLOAT: 32-bit floating point number.
    INT64: 64-bit signed integer.
    UINT64: 64-bit unsigned integer.
    INT32: 32-bit signed integer.
    BOOL: Boolean value (True or False).
    STRING: String of UTF-8 encoded text.
    MESSAGE: Embedded message as byte string.
    BYTES: String of 8-bit bytes.
    UINT32: 32-bit unsigned integer.
    ENUM: Enum value as integer.
    SINT32: 32-bit signed integer.  Uses "zig-zag" encoding.
    SINT64: 64-bit signed integer.  Uses "zig-zag" encoding.
  """
  DOUBLE   = 1
  FLOAT    = 2
  INT64    = 3
  UINT64   = 4
  INT32    = 5
  BOOL     = 8
  STRING   = 9
  MESSAGE  = 11
  BYTES    = 12
  UINT32   = 13
  ENUM     = 14
  SINT32   = 17
  SINT64   = 18


def defaultValue(Enum_class, value):
  if issubclass(Enum_class, Enum):
    Enum_class.__class__.set_default(Enum_class, value)