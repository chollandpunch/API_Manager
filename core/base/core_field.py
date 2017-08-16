import six

import core.core_constants as constants
import core.core_utils as util
from core.errors_old.core_error import *
from core.base.core_enum import *
from core.utils import validation_util

__all__ =['FieldList', 'Field', '_FieldMeta',
          'IntegerField', 'FloatField', 'BooleanField',
          'BytesField', 'StringField']

class FieldList(list):
  """List implementation that validates field values.
  This list implementation overrides all methods that add values in to a list
  in order to validate those new elements.  Attempting to add or set list
  values that are not of the correct type will raise ValidationError.
  """

  def __init__(self, field_instance, sequence):
    """Constructor.
    Args:
      field_instance: Instance of field that validates the list.
      sequence: List or tuple to construct list from.
    """
    if not field_instance.repeated:
      raise FieldDefinitionError('FieldList may only accept repeated fields')
    self.__field = field_instance
    self.__field.validate(sequence)
    list.__init__(self, sequence)

  def __getstate__(self):
    """Enable pickling.
    The assigned field instance can't be pickled if it belongs to a Message
    definition (message_definition uses a weakref), so the Message class and
    field number are returned in that case.
    Returns:
      A 3-tuple containing:
        - The field instance, or None if it belongs to a Message class.
        - The Message class that the field instance belongs to, or None.
        - The field instance number of the Message class it belongs to, or None.
    """
    message_class = self.__field.message_definition()
    if message_class is None:
      return self.__field, None, None
    else:
      return None, message_class, self.__field.number

  def __setstate__(self, state):
    """Enable unpickling.
    Args:
      state: A 3-tuple containing:
        - The field instance, or None if it belongs to a Message class.
        - The Message class that the field instance belongs to, or None.
        - The field instance number of the Message class it belongs to, or None.
    """
    field_instance, message_class, number = state
    if field_instance is None:
      self.__field = message_class.field_by_number(number)
    else:
      self.__field = field_instance

  @property
  def field(self):
    """Field that validates list."""
    return self.__field

  def __setslice__(self, i, j, sequence):
    """Validate slice assignment to list."""
    self.__field.validate(sequence)
    list.__setslice__(self, i, j, sequence)

  def __setitem__(self, index, value):
    """Validate item assignment to list."""
    if isinstance(index, slice):
        self.__field.validate(value)
    else:
        self.__field.validate_element(value)
    list.__setitem__(self, index, value)

  def append(self, value):
    """Validate item appending to list."""
    self.__field.validate_element(value)
    return list.append(self, value)

  def extend(self, sequence):
    """Validate extension of list."""
    self.__field.validate(sequence)
    return list.extend(self, sequence)

  def insert(self, index, value):
    """Validate item insertion to list."""
    self.__field.validate_element(value)
    return list.insert(self, index, value)


class _FieldMeta(type):

  def __init__(cls, name, bases, dct):
    getattr(cls, '_Field__variant_to_type').update(
      (variant, cls) for variant in dct.get('VARIANTS', []))
    type.__init__(cls, name, bases, dct)


class Field(object):

  __initialized = False
  __variant_to_type = {}

  __metaclass__ = _FieldMeta

  @util.positional(2)
  def __init__(self,
               number,
               required=False,
               repeated=False,
               variant=None,
               default=None):
    """Constructor.
    The required and repeated parameters are mutually exclusive.  Setting both
    to True will raise a FieldDefinitionError.
    Sub-class Attributes:
      Each sub-class of Field must define the following:
        VARIANTS: Set of variant types accepted by that field.
        DEFAULT_VARIANT: Default variant type if not specified in constructor.
    Args:
      number: Number of field.  Must be unique per message class.
      required: Whether or not field is required.  Mutually exclusive with
        'repeated'.
      repeated: Whether or not field is repeated.  Mutually exclusive with
        'required'.
      variant: Wire-format variant hint.
      default: Default value for field if not found in stream.
    Raises:
      InvalidVariantError when invalid variant for field is provided.
      InvalidDefaultError when invalid default for field is provided.
      FieldDefinitionError when invalid number provided or mutually exclusive
        fields are used.
      InvalidNumberError when the field number is out of range or reserved.
    """
    if not isinstance(number, int) or not 1 <= number <= constants.MAX_FIELD_NUMBER:
      raise InvalidNumberError('Invalid number for field: %s'
                                     '\nNumber must be 1 or greater and %d or less' %
                                     (number, constants.MAX_FIELD_NUMBER))

    if constants.FIRST_RESERVED_FIELD_NUMBER <= number <= constants.LAST_RESERVED_FIELD_NUMBER:
      raise InvalidNumberError('Tag number %d is a reserved number.\n'
                                     'Numbers %d to %d are reserved' %
                                     (number, constants.FIRST_RESERVED_FIELD_NUMBER,
                                      constants.LAST_RESERVED_FIELD_NUMBER))

    if repeated and required:
      raise FieldDefinitionError('Cannot set both repeated and required')

    if variant is None:
      variant = self.DEFAULT_VARIANT

    if repeated and default is not None:
      raise FieldDefinitionError('Repeated fields may not have defaults')

    if variant not in self.VARIANTS:
      raise InvalidVariantError('Invalid variant: %s\n'
                                      'Valid variants for %s are %r' %
                                      (variant, type(self).__name__, sorted(self.VARIANTS)))

    self.number = number
    self.required = required
    self.repeated = repeated
    self.variant = variant

    if default is not None:
      try:
        self.validate_default(default)
      except ValidationError as err:
        try:
          name = self.name
        except AttributeError:
          # For when raising error before name initialization.
          raise InvalidDefaultError('Invalid default value for %s: %r: %s' %
                                          (self.__class__.__name__, default, err))
        else:
          raise InvalidDefaultError('Invalid default value for field %s:'
                                          '%r: %s' % (name, default, err))

    self.__default = default

    if not issubclass(self.__class__, ExpandedField):
      self.__initialized = True

  def __setattr__(self, name, value):
    """Setter overidden to prevent assignment to fields after creation.
    Args:
      name: Name of attribute to set.
      value: Value to assign.
    """
    # Special case post-init names.  They need to be set after constructor.
    if name in constants._POST_INIT_FIELD_ATTRIBUTE_NAMES:
      object.__setattr__(self, name, value)
      return

    # All other attributes must be set before __initialized.
    if not self.__initialized:
      # Not initialized yet, allow assignment.
      object.__setattr__(self, name, value)
    else:
      raise AttributeError('Field objects are read-only')

  def __set__(self, message_instance, value):
    """Set value on message.
    Args:
      message_instance: Message instance to set value on.
      value: Value to set on message.
    """
    # Reaches in to message instance directly to assign to private tags.
    if value is None:
      if self.repeated:
        raise ValidationError(
          'May not assign None to repeated field %s' % self.name)
      else:
        message_instance._Message__tags.pop(self.number, None)
    else:
      if self.repeated:
        value = FieldList(self, value)
      else:
        value = self.validate(value)
      message_instance._Message__tags[self.number] = value

  def __get__(self, message_instance, message_class):
    if message_instance is None:
      return self

    result = message_instance._Message__tags.get(self.number)
    if result is None:
      return self.default
    else:
      return result

  def validate_element(self, value):
    """Validate single element of field.
    This is different from validate in that it is used on individual
    values of repeated fields.
    Args:
      value: Value to validate.
    Returns:
      The value casted in the expected type.
    Raises:
      ValidationError if value is not expected type.
    """

    if not isinstance(value, self.type):
      # Authorize in values as float
      if isinstance(value, six.integer_types) and self.type == float:
        return float(value)

      if value is None:
        if self.required:
          raise ValidationError('Required field is missing')
      else:
        try:
          name = self.name
        except AttributeError:
          raise ValidationError('Expected type %s for %s, '
                                'found %s (type %s)' %
                                (self.type, self.__class__.__name__,
                                 value, type(value)))
        else:
          raise ValidationError('Expected type %s for field %s, '
                                'found %s (type %s)' %
                                (self.type, name, value, type(value)))
    return value

  def __validate(self, value, validate_element):
    """Internal validation function.
    Validate an internal value using a function to validate individual elements.
    Args:
      value: Value to validate.
      validate_element: Function to use to validate individual elements.
    Raises:
      ValidationError if value is not expected type.
    """
    if not self.repeated:
      return validate_element(value)
    else:
      # Must be a list or tuple, may not be a string.
      if isinstance(value, (list, tuple)):
        result = []
        for element in value:
          if element is None:
            try:
              name = self.name
            except AttributeError:
              raise ValidationError('Repeated values for %s '
                                    'may not be None' % self.__class__.__name__)
            else:
              raise ValidationError('Repeated values for field %s '
                                    'may not be None' % name)
          result.append(validate_element(element))
        return result
      elif value is not None:
        try:
          name = self.name
        except AttributeError:
          raise ValidationError('%s is repeated. Found: %s' % (
            self.__class__.__name__, value))
        else:
          raise ValidationError('Field %s is repeated. Found: %s' % (name,
                                                                     value))
    return value

  def validate(self, value):
    """Validate value assigned to field.
    Args:
      value: Value to validate.
    Returns:
      the value eventually casted in the correct type.
    Raises:
      ValidationError if value is not expected type.
    """
    return self.__validate(value, self.validate_element)

  def validate_default_element(self, value):
    """Validate value as assigned to field default field.
    Some fields may allow for delayed resolution of default types necessary
    in the case of circular definition references.  In this case, the default
    value might be a place holder that is resolved when needed after all the
    message classes are defined.
    Args:
      value: Default value to validate.
    Returns:
      the value eventually casted in the correct type.
    Raises:
      ValidationError if value is not expected type.
    """
    return self.validate_element(value)

  def validate_default(self, value):
    """Validate default value assigned to field.
    Args:
      value: Value to validate.
    Returns:
      the value eventually casted in the correct type.
    Raises:
      ValidationError if value is not expected type.
    """
    return self.__validate(value, self.validate_default_element)

  def message_definition(self):
    """Get Message definition that contains this Field definition.
    Returns:
      Containing Message definition for Field.  Will return None if for
      some reason Field is defined outside of a Message class.
    """
    try:
      return self._message_definition()
    except AttributeError:
      return None

  @property
  def default(self):
    """Get default value for field."""
    return self.__default

  @classmethod
  def lookup_field_type_by_variant(cls, variant):
    return cls.__variant_to_type[variant]

# Not sure if ExpandedField is causing problems
class ExpandedField(object):
  pass
# class ExpandedField(Field):
#   def __init__(self, number,
#                required=False,
#                repeated=False,
#                variant=None,
#                default=None,
#                mutable=True,
#                lockable=True,
#                aliases=[],
#                description=None):
#     super(ExpandedField, self).__init__(number, required=required, repeated=repeated,
#                                         variant=variant, default=default)
#
#
#     if not isinstance(aliases, list) or any(
#             [not isinstance(x, str) for x in aliases]):
#       raise TypeError('Aliases must be list of string '
#                       'types: {0}'.format(aliases))
#
#     if not isinstance(mutable, bool):
#       raise TypeError('Mutable must be Boolean value: {0}'.format(mutable))
#
#     if not isinstance(lockable, bool):
#       raise TypeError('Lockable must be Boolean value: {0}'.format(lockable))
#
#     if not mutable and not lockable:
#       raise FieldDefinitionError('Cannot be both immutable and non-lockable.')
#
#     self.mutable = mutable
#     self.lockable = lockable
#     self.aliases = aliases
#     self.description = description
#     self.__initialized = True

class IntegerField(Field):
  """Field definition for integer values."""

  VARIANTS = frozenset([Variant.INT32,
                        Variant.INT64,
                        Variant.UINT32,
                        Variant.UINT64,
                        Variant.SINT32,
                        Variant.SINT64,
                       ])

  DEFAULT_VARIANT = Variant.INT64

  type = six.integer_types


class FloatField(Field):
  """Field definition for float values."""

  VARIANTS = frozenset([Variant.FLOAT,
                        Variant.DOUBLE,
                       ])

  DEFAULT_VARIANT = Variant.DOUBLE

  type = float


class BooleanField(Field):
  """Field definition for boolean values."""

  VARIANTS = frozenset([Variant.BOOL])

  DEFAULT_VARIANT = Variant.BOOL

  type = bool


class BytesField(Field):
  """Field definition for byte string values."""

  VARIANTS = frozenset([Variant.BYTES])

  DEFAULT_VARIANT = Variant.BYTES

  type = bytes


class StringField(Field):
  """Field definition for unicode string values."""

  VARIANTS = frozenset([Variant.STRING])

  DEFAULT_VARIANT = Variant.STRING

  type = six.text_type

  def validate_element(self, value):
    """Validate StringField allowing for str and unicode.
    Raises:
      ValidationError if a str value is not 7-bit ascii..
    """
    # If value is str is it considered valid.  Satisfies "required=True".

    if isinstance(value, bytes):
      try:
        six.text_type(value, 'ascii')
      except UnicodeDecodeError as err:
        try:
          name = self.name
        except AttributeError:
          validation_error = ValidationError(
            'Field encountered non-ASCII string %r: %s' % (value,
                                                           err))
        else:
          validation_error = ValidationError(
            'Field %s encountered non-ASCII string %r: %s' % (self.name,
                                                              value,
                                                              err))
          validation_field_name = self.name
        raise validation_error
      return value
    else:
      return super(StringField, self).validate_element(value)


class EmailField(StringField):
  """Field definition for email address values."""

  def validate_element(self, value):
    """Validates field value as first a string, then a valid email address."""
    if super(EmailField, self).validate_element(value):
      valid_uname, valid_domain = validation_util.valid_email(value)
      if not (valid_uname and valid_domain):
        if isinstance(valid_domain, int):
          val_error = ValidationError(
            'Field encountered improperly formatted email address: %s' % value)
        else:
          if '@' not in value:
            val_error = ValidationError(
            'Field encountered email address with missing @ '
            'character: %s' % value)
          else:
            val_error = ValidationError(
              'Field encountered email address with illegal '
              'characters: %s' % value)

        raise val_error
      else:
        return value


