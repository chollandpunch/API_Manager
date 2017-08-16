"""Stand-alone implementation of in memory protocol messages.
Public Classes:
  Enum: Represents an enumerated type.
  Variant: Hint for wire format to determine how to serialize.
  Message: Base class for user defined messages.
  IntegerField: Field for integer values.
  FloatField: Field for float values.
  BooleanField: Field for boolean values.
  BytesField: Field for binary string values.
  StringField: Field for UTF-8 string values.
  MessageField: Field for other message type values.
  EnumField: Field for enumerated type values.
Public Exceptions (indentation indications class hierarchy):
  EnumDefinitionError: Raised when enumeration is incorrectly defined.
  FieldDefinitionError: Raised when field is incorrectly defined.
    InvalidVariantError: Raised when variant is not compatible with field type.
    InvalidDefaultError: Raised when default is not compatiable with field.
    InvalidNumberError: Raised when field number is out of range or reserved.
  MessageDefinitionError: Raised when message is incorrectly defined.
    DuplicateNumberError: Raised when field has duplicate number with another.
  ValidationError: Raised when a message or field is not valid.
  DefinitionNotFoundError: Raised when definition not found.
"""

import six
import types
import weakref

from core.base.core_field import *
from core.base.core_enum import *
from core.errors.core_error import *
from core.base.meta.core_definition import *
import core.core_constants as constants
import core.core_utils as util


class _MessageClass(_DefinitionClass):
  """Meta-class used for defining the Message base class.
  For more details about Message classes, see the Message class docstring.
  Information contained there may help understanding this class.
  Meta-class enables very specific behavior for any defined Message
  class.  All attributes defined on an Message sub-class must be field
  instances, Enum class definitions or other Message class definitions.  Each
  field attribute defined on an Message sub-class is added to the set of
  field definitions and the attribute is translated in to a slot.  It also
  ensures that only one level of Message class hierarchy is possible.  In other
  words it is not possible to declare sub-classes of sub-classes of
  Message.
  This class also defines some functions in order to restrict the
  behavior of the Message class and its sub-classes.  It is not possible
  to change the behavior of the Message class in later classes since
  any new classes may be defined with only field, Enums and Messages, and
  no methods.
  """

  def __new__(cls, name, bases, dct):
    """Create new Message class instance.
    The __new__ method of the _MessageClass type is overridden so as to
    allow the translation of Field instances to slots.
    """
    by_number = {}
    by_name = {}

    variant_map = {}

    if bases != (object,):
      # Can only define one level of sub-classes below Message.
      if bases != (Message,):
        raise MessageDefinitionError('Message types may only inherit from Message')

      enums = []
      messages = []
      # Must not use iteritems because this loop will change the state of dct.
      for key, field_type in dct.items():

        if key in constants._RESERVED_ATTRIBUTE_NAMES:
          continue

        if isinstance(field_type, type) and issubclass(field_type, Enum):
          enums.append(key)
          continue

        if (isinstance(field_type, type) and
            issubclass(field_type, Message) and
            field_type is not Message):
          messages.append(key)
          continue

        # Reject anything that is not a field.
        if type(field_type) is Field or not issubclass(type(field_type), Field):
          raise MessageDefinitionError(
              'May only use fields in message definitions.  Found: %s = %s' %
              (key, field_type))

        if field_type.number in by_number:
          raise DuplicateNumberError(
              'Field with number %d declared more than once in %s' %
              (field_type.number, name))

        field_type.name = key

        # Place in name and number maps.
        by_name[key] = field_type
        by_number[field_type.number] = field_type

      # Add enums if any exist.
      if enums:
        dct['__enums__'] = sorted(enums)

      # Add messages if any exist.
      if messages:
        dct['__messages__'] = sorted(messages)

    dct['_Message__by_number'] = by_number
    dct['_Message__by_name'] = by_name

    return _DefinitionClass.__new__(cls, name, bases, dct)

  def __init__(cls, name, bases, dct):
    """Initializer required to assign references to new class."""
    if bases != (object,):
      for value in dct.values():
        if isinstance(value, _DefinitionClass) and not value is Message:
          value._message_definition = weakref.ref(cls)

      for f in cls.all_fields():
        f._message_definition = weakref.ref(cls)

    _DefinitionClass.__init__(cls, name, bases, dct)


class Message(object):
  """Base class for user defined message objects.
  Used to define messages for efficient transmission across network or
  process space.  Messages are defined using the field classes (IntegerField,
  FloatField, EnumField, etc.).
  Messages are more restricted than normal classes in that they may only
  contain field attributes and other Message and Enum definitions.  These
  restrictions are in place because the structure of the Message class is
  intentended to itself be transmitted across network or process space and
  used directly by clients or even other servers.  As such methods and
  non-field attributes could not be transmitted with the structural information
  causing discrepancies between different languages and implementations.
  Initialization and validation:
    A Message object is considered to be initialized if it has all required
    fields and any nested messages are also initialized.
    Calling 'check_initialized' will raise a ValidationException if it is not
    initialized; 'is_initialized' returns a boolean value indicating if it is
    valid.
    Validation automatically occurs when Message objects are created
    and populated.  Validation that a given value will be compatible with
    a field that it is assigned to can be done through the Field instances
    validate() method.  The validate method used on a message will check that
    all values of a message and its sub-messages are valid.  Assigning an
    invalid value to a field will raise a ValidationException.
  Example:
    # Trade type.
    class TradeType(Enum):
      BUY = 1
      SELL = 2
      SHORT = 3
      CALL = 4
    class Lot(Message):
      price = IntegerField(1, required=True)
      quantity = IntegerField(2, required=True)
    class Order(Message):
      symbol = StringField(1, required=True)
      total_quantity = IntegerField(2, required=True)
      trade_type = EnumField(TradeType, 3, required=True)
      lots = MessageField(Lot, 4, repeated=True)
      limit = IntegerField(5)
    order = Order(symbol='GOOG',
                  total_quantity=10,
                  trade_type=TradeType.BUY)
    lot1 = Lot(price=304,
               quantity=7)
    lot2 = Lot(price = 305,
               quantity=3)
    order.lots = [lot1, lot2]
    # Now object is initialized!
    order.check_initialized()
  """
  __metaclass__ = _MessageClass
  def __init__(self, **kwargs):
    """Initialize internal messages state.
    Args:
      A message can be initialized via the constructor by passing in keyword
      arguments corresponding to fields.  For example:
        class Date(Message):
          day = IntegerField(1)
          month = IntegerField(2)
          year = IntegerField(3)
      Invoking:
        date = Date(day=6, month=6, year=1911)
      is the same as doing:
        date = Date()
        date.day = 6
        date.month = 6
        date.year = 1911
    """
    # Tag being an essential implementation detail must be private.
    self.__tags = {}
    self.__unrecognized_fields = {}

    assigned = set()
    for name, value in kwargs.items():

      setattr(self, name, value)
      assigned.add(name)
    # initialize repeated fields.
    for f in self.all_fields():
      if f.repeated and f.name not in assigned:
        setattr(self, f.name, [])


  def check_initialized(self):
    """Check class for initialization status.
    Check that all required fields are initialized
    Raises:
      ValidationError: If message is not initialized.
    """
    for name, mfield in self.__by_name.items():
      value = getattr(self, name)
      if value is None:
        if mfield.required:
          raise ValidationError("Message %s is missing required field %s" %
                                (type(self).__name__, name))
      else:
        try:
          if (isinstance(mfield, MessageField) and
              issubclass(mfield.message_type, Message)):
            if mfield.repeated:
              for item in value:
                item_message_value = mfield.value_to_message(item)
                item_message_value.check_initialized()
            else:
              message_value = mfield.value_to_message(value)
              message_value.check_initialized()
        except ValidationError as err:
          if not hasattr(err, 'message_name'):
            err.message_name = type(self).__name__
          raise

  def is_initialized(self):
    """Get initialization status.
    Returns:
      True if message is valid, else False.
    """
    try:
      self.check_initialized()
    except ValidationError:
      return False
    else:
      return True

  @classmethod
  def all_fields(cls):
    """Get all field definition objects.
    Ordering is arbitrary.
    Returns:
      Iterator over all values in arbitrary order.
    """
    return cls.__by_name.values()

  @classmethod
  def field_by_name(cls, name):
    """Get field by name.
    Returns:
      Field object associated with name.
    Raises:
      KeyError if no field found by that name.
    """
    return cls.__by_name[name]

  @classmethod
  def field_by_number(cls, number):
    """Get field by number.
    Returns:
      Field object associated with number.
    Raises:
      KeyError if no field found by that number.
    """
    return cls.__by_number[number]

  def get_assigned_value(self, name):
    """Get the assigned value of an attribute.
    Get the underlying value of an attribute.  If value has not been set, will
    not return the default for the field.
    Args:
      name: Name of attribute to get.
    Returns:
      Value of attribute, None if it has not been set.
    """
    message_type = type(self)
    try:
      mfield = message_type.field_by_name(name)
    except KeyError:
      raise AttributeError('Message %s has no field %s' % (
          message_type.__name__, name))
    return self.__tags.get(mfield.number)

  def reset(self, name):
    """Reset assigned value for field.
    Resetting a field will return it to its default value or None.
    Args:
      name: Name of field to reset.
    """
    message_type = type(self)
    try:
      mfield = message_type.field_by_name(name)
    except KeyError:
      if name not in message_type.__by_name:
        raise AttributeError('Message %s has no field %s' % (
            message_type.__name__, name))
    if mfield.repeated:
      self.__tags[mfield.number] = FieldList(mfield, [])
    else:
      self.__tags.pop(mfield.number, None)

  def all_unrecognized_fields(self):
    """Get the names of all unrecognized fields in this message."""
    return list(self.__unrecognized_fields.keys())

  def get_unrecognized_field_info(self, key, value_default=None,
                                  variant_default=None):
    """Get the value and variant of an unknown field in this message.
    Args:
      key_bk: The name or number of the field to retrieve.
      value_default: Value to be returned if the key_bk isn't found.
      variant_default: Value to be returned as variant if the key_bk isn't
        found.
    Returns:
      (value, variant), where value and variant are whatever was passed
      to set_unrecognized_field.
    """
    value, variant = self.__unrecognized_fields.get(key, (value_default,
                                                          variant_default))
    return value, variant

  def set_unrecognized_field(self, key, value, variant):
    """Set an unrecognized field, used when decoding a message.
    Args:
      key_bk: The name or number used to refer to this unknown value.
      value: The value of the field.
      variant: Type information needed to interpret the value or re-encode it.
    Raises:
      TypeError: If the variant is not an instance of messages.Variant.
    """
    if not isinstance(variant, Variant):
      raise TypeError('Variant type %s is not valid.' % variant)
    self.__unrecognized_fields[key] = value, variant

  def __setattr__(self, name, value):
    """Change set behavior for messages.
    Messages may only be assigned values that are fields.
    Does not try to validate field when set.
    Args:
      name: Name of field to assign to.
      value: Value to assign to field.
    Raises:
      AttributeError when trying to assign value that is not a field.
    """
    if name in self.__by_name or name.startswith('_Message__'):
      object.__setattr__(self, name, value)
    else:
      raise AttributeError("May not assign arbitrary value %s "
                           "to message %s" % (name, type(self).__name__))

  def __repr__(self):
    """Make string representation of message.
    Example:
      class MyMessage(messages.Message):
        integer_value = messages.IntegerField(1)
        string_value = messages.StringField(2)
      my_message = MyMessage()
      my_message.integer_value = 42
      my_message.string_value = u'A string'
      print my_message
      >>> <MyMessage
      ...  integer_value: 42
      ...  string_value: u'A string'>
    Returns:
      String representation of message, including the values
      of all fields and repr of all sub-messages.
    """
    body = ['<', type(self).__name__]
    for mfield in sorted(self.all_fields(),
                        key=lambda f: f.number):
      attribute = mfield.name
      value = self.get_assigned_value(mfield.name)
      if value is not None:
        body.append('\n %s: %s' % (attribute, repr(value)))
    body.append('>')
    return ''.join(body)

  def __eq__(self, other):
    """Equality operator.
    Does field by field comparison with other message.  For
    equality, must be same type and values of all fields must be
    equal.
    Messages not required to be initialized for comparison.
    Does not attempt to determine equality for values that have
    default values that are not set.  In other words:
      class HasDefault(Message):
        attr1 = StringField(1, default='default value')
      message1 = HasDefault()
      message2 = HasDefault()
      message2.attr1 = 'default value'
      message1 != message2
    Does not compare unknown values.
    Args:
      other: Other message to compare with.
    """

    if self is other:
      return True

    if type(self) is not type(other):
      return False

    return self.__tags == other.__tags

  def __ne__(self, other):
    """Not equals operator.
    Does field by field comparison with other message.  For
    non-equality, must be different type or any value of a field must be
    non-equal to the same field in the other instance.
    Messages not required to be initialized for comparison.
    Args:
      other: Other message to compare with.
    """
    return not self.__eq__(other)


class MessageField(Field):
  """Field definition for sub-message values.
  Message fields contain instance of other messages.  Instances stored
  on messages stored on message fields  are considered to be owned by
  the containing message instance and should not be shared between
  owning instances.
  Message fields must be defined to reference a single type of message.
  Normally message field are defined by passing the referenced message
  class in to the constructor.
  It is possible to define a message field for a type that does not yet
  exist by passing the name of the message in to the constructor instead
  of a message class.  Resolution of the actual type of the message is
  deferred until it is needed, for example, during message verification.
  Names provided to the constructor must refer to a class within the same
  python module as the class that is using it.  Names refer to messages
  relative to the containing messages scope.  For example, the two fields
  of OuterMessage refer to the same message type:
    class Outer(Message):
      inner_relative = MessageField('Inner', 1)
      inner_absolute = MessageField('Outer.Inner', 2)
      class Inner(Message):
        ...
  When resolving an actual type, MessageField will traverse the entire
  scope of nested messages to match a message name.  This makes it easy
  for siblings to reference siblings:
    class Outer(Message):
      class Inner(Message):
        sibling = MessageField('Sibling', 1)
      class Sibling(Message):
        ...
  """

  VARIANTS = frozenset([Variant.MESSAGE])

  DEFAULT_VARIANT = Variant.MESSAGE

  @util.positional(3)
  def __init__(self,
               message_type,
               number,
               required=False,
               repeated=False,
               variant=None):
    """Constructor.
    Args:
      message_type: Message type for field.  Must be subclass of Message.
      number: Number of field.  Must be unique per message class.
      required: Whether or not field is required.  Mutually exclusive to
        'repeated'.
      repeated: Whether or not field is repeated.  Mutually exclusive to
        'required'.
      variant: Wire-format variant hint.
    Raises:
      FieldDefinitionError when invalid message_type is provided.
    """
    valid_type = (isinstance(message_type, six.string_types) or
                  (message_type is not Message and
                   isinstance(message_type, type) and
                   issubclass(message_type, Message)))

    if not valid_type:
      raise FieldDefinitionError('Invalid message class: %s' % message_type)

    if isinstance(message_type, six.string_types):
      self.__type_name = message_type
      self.__type = None
    else:
      self.__type = message_type

    super(MessageField, self).__init__(number,
                                       required=required,
                                       repeated=repeated,
                                       variant=variant)

  def __set__(self, message_instance, value):
    """Set value on message.
    Args:
      message_instance: Message instance to set value on.
      value: Value to set on message.
    """
    message_type = self.type
    if isinstance(message_type, type) and issubclass(message_type, Message):
      if self.repeated:
        if value and isinstance(value, (list, tuple)):
          value = [(message_type(**v) if isinstance(v, dict) else v)
                   for v in value]
      elif isinstance(value, dict):
        value = message_type(**value)
    super(MessageField, self).__set__(message_instance, value)

  @property
  def type(self):
    """Message type used for field."""
    if self.__type is None:
      message_type = find_definition(self.__type_name, self.message_definition())
      if not (message_type is not Message and
              isinstance(message_type, type) and
              issubclass(message_type, Message)):
        raise FieldDefinitionError('Invalid message class: %s' % message_type)
      self.__type = message_type
    return self.__type

  @property
  def message_type(self):
    """Underlying message type used for serialization.
    Will always be a sub-class of Message.  This is different from type
    which represents the python value that message_type is mapped to for
    use by the user.
    """
    return self.type

  def value_from_message(self, message):
    """Convert a message to a value instance.
    Used by deserializers to convert from underlying messages to
    value of expected user type.
    Args:
      message: A message instance of type self.message_type.
    Returns:
      Value of self.message_type.
    """
    if not isinstance(message, self.message_type):
      raise DecodeError('Expected type %s, got %s: %r' %
                        (self.message_type.__name__,
                         type(message).__name__,
                         message))
    return message

  def value_to_message(self, value):
    """Convert a value instance to a message.
    Used by serializers to convert Python user types to underlying
    messages for transmission.
    Args:
      value: A value of type self.type.
    Returns:
      An instance of type self.message_type.
    """
    if not isinstance(value, self.type):
      raise EncodeError('Expected type %s, got %s: %r' %
                        (self.type.__name__,
                         type(value).__name__,
                         value))
    return value


class EnumField(Field):
  """Field definition for enum values.
  Enum fields may have default values that are delayed until the associated enum
  type is resolved.  This is necessary to support certain circular references.
  For example:
    class Message1(Message):
      class Color(Enum):
        RED = 1
        GREEN = 2
        BLUE = 3
      # This field default value  will be validated when default is accessed.
      animal = EnumField('Message2.Animal', 1, default='HORSE')
    class Message2(Message):
      class Animal(Enum):
        DOG = 1
        CAT = 2
        HORSE = 3
      # This fields default value will be validated right away since Color is
      # already fully resolved.
      color = EnumField(Message1.Color, 1, default='RED')
  """

  VARIANTS = frozenset([Variant.ENUM])

  DEFAULT_VARIANT = Variant.ENUM

  def __init__(self, enum_type, number, **kwargs):
    """Constructor.
    Args:
      enum_type: Enum type for field.  Must be subclass of Enum.
      number: Number of field.  Must be unique per message class.
      required: Whether or not field is required.  Mutually exclusive to
        'repeated'.
      repeated: Whether or not field is repeated.  Mutually exclusive to
        'required'.
      variant: Wire-format variant hint.
      default: Default value for field if not found in stream.
    Raises:
      FieldDefinitionError when invalid enum_type is provided.
    """
    valid_type = (isinstance(enum_type, six.string_types) or
                  (enum_type is not Enum and
                   isinstance(enum_type, type) and
                   issubclass(enum_type, Enum)))

    if not valid_type:
      raise FieldDefinitionError('Invalid enum type: %s' % enum_type)

    if isinstance(enum_type, six.string_types):
      self.__type_name = enum_type
      self.__type = None
    else:
      self.__type = enum_type

    super(EnumField, self).__init__(number, **kwargs)

  def validate_default_element(self, value):
    """Validate default element of Enum field.
    Enum fields allow for delayed resolution of default values when the type
    of the field has not been resolved.  The default value of a field may be
    a string or an integer.  If the Enum type of the field has been resolved,
    the default value is validated against that type.
    Args:
      value: Value to validate.
    Raises:
      ValidationError if value is not expected message type.
    """
    if isinstance(value, (six.string_types, six.integer_types)):
      # Validation of the value does not happen for delayed resolution
      # enumerated types.  Ignore if type is not yet resolved.
      if self.__type:
        self.__type(value)
      return

    return super(EnumField, self).validate_default_element(value)

  @property
  def type(self):
    """Enum type used for field."""
    if self.__type is None:
      found_type = find_definition(self.__type_name, self.message_definition())
      if not (found_type is not Enum and
              isinstance(found_type, type) and
              issubclass(found_type, Enum)):
        raise FieldDefinitionError('Invalid enum type: %s' % found_type)

      self.__type = found_type
    return self.__type

  @property
  def default(self):
    """Default for enum field.
    Will cause resolution of Enum type and unresolved default value.
    """
    try:
      return self.__resolved_default
    except AttributeError:
      resolved_default = super(EnumField, self).default
      if isinstance(resolved_default, (six.string_types, six.integer_types)):
        resolved_default = self.type(resolved_default)
      self.__resolved_default = resolved_default
      return self.__resolved_default


@util.positional(2)
def find_definition(name, relative_to=None, importer=__import__):
  """Find definition by name in module-space.
  The find algorthm will look for definitions by name relative to a message
  definition or by fully qualfied name.  If no definition is found relative
  to the relative_to parameter it will do the same search against the container
  of relative_to.  If relative_to is a nested Message, it will search its
  message_definition().  If that message has no message_definition() it will
  search its module.  If relative_to is a module, it will attempt to look for
  the containing module and search relative to it.  If the module is a top-level
  module, it will look for the a message using a fully qualified name.  If
  no message is found then, the search fails and DefinitionNotFoundError is
  raised.
  For example, when looking for any definition 'foo.bar.ADefinition' relative to
  an actual message definition abc.xyz.SomeMessage:
    find_definition('foo.bar.ADefinition', SomeMessage)
  It is like looking for the following fully qualified names:
    abc.xyz.SomeMessage. foo.bar.ADefinition
    abc.xyz. foo.bar.ADefinition
    abc. foo.bar.ADefinition
    foo.bar.ADefinition
  When resolving the name relative to Message definitions and modules, the
  algorithm searches any Messages or sub-modules found in its path.
  Non-Message values are not searched.
  A name that begins with '.' is considered to be a fully qualified name.  The
  name is always searched for from the topmost package.  For example, assume
  two message types:
    abc.xyz.SomeMessage
    xyz.SomeMessage
  Searching for '.xyz.SomeMessage' relative to 'abc' will resolve to
  'xyz.SomeMessage' and not 'abc.xyz.SomeMessage'.  For this kind of name,
  the relative_to parameter is effectively ignored and always set to None.
  For more information about package name resolution, please see:
    http://code.google.com/apis/protocolbuffers/docs/proto.html#packages
  Args:
    name: Name of definition to find.  May be fully qualified or relative name.
    relative_to: Search for definition relative to message definition or module.
      None will cause a fully qualified name search.
    importer: Import function to use for resolving modules.
  Returns:
    Enum or Message class definition associated with name.
  Raises:
    DefinitionNotFoundError if no definition is found in any search path.
  """
  # Check parameters.
  if not (relative_to is None or
          isinstance(relative_to, types.ModuleType) or
          isinstance(relative_to, type) and issubclass(relative_to, Message)):
    raise TypeError('relative_to must be None, Message definition or module.  '
                    'Found: %s' % relative_to)

  name_path = name.split('.')

  # Handle absolute path reference.
  if not name_path[0]:
    relative_to = None
    name_path = name_path[1:]

  def search_path():
    """Performs a single iteration searching the path from relative_to.
    This is the function that searches up the path from a relative object.
      fully.qualified.object . relative.or.nested.Definition
                               ---------------------------->
                                                  ^
                                                  |
                            this part of search --+
    Returns:
      Message or Enum at the end of name_path, else None.
    """
    next = relative_to
    for node in name_path:
      # Look for attribute first.
      attribute = getattr(next, node, None)

      if attribute is not None:
        next = attribute
      else:
        # If module, look for sub-module.
        if next is None or isinstance(next, types.ModuleType):
          if next is None:
            module_name = node
          else:
            module_name = '%s.%s' % (next.__name__, node)

          try:
            fromitem = module_name.split('.')[-1]
            next = importer(module_name, '', '', [str(fromitem)])
          except ImportError:
            return None
        else:
          return None

      if (not isinstance(next, types.ModuleType) and
          not (isinstance(next, type) and
               issubclass(next, (Message, Enum)))):
        return None

    return next

  while True:
    found = search_path()
    if isinstance(found, type) and issubclass(found, (Enum, Message)):
      return found
    else:
      # Find next relative_to to search against.
      #
      #   fully.qualified.object . relative.or.nested.Definition
      #   <---------------------
      #           ^
      #           |
      #   does this part of search
      if relative_to is None:
        # Fully qualified search was done.  Nothing found.  Fail.
        raise DefinitionNotFoundError('Could not find definition for %s'
                                      % (name,))
      else:
        if isinstance(relative_to, types.ModuleType):
          # Find parent module.
          module_path = relative_to.__name__.split('.')[:-1]
          if not module_path:
            relative_to = None
          else:
            # Should not raise ImportError.  If it does... weird and
            # unexepected.  Propagate.
            relative_to = importer(
              '.'.join(module_path), '', '', [module_path[-1]])
        elif (isinstance(relative_to, type) and
              issubclass(relative_to, Message)):
          parent = relative_to.message_definition()
          if parent is None:
            last_module_name = relative_to.__module__.split('.')[-1]
            relative_to = importer(
              relative_to.__module__, '', '', [last_module_name])
          else:
            relative_to = parent


# Dummy Message
class TradeType(Enum):
  BUY = 1
  SELL = 2
  SHORT = 3
  CALL = 4

class Lot(Message):
  price = IntegerField(1, required=True)
  quantity = IntegerField(2, required=True)

class Order(Message):
  symbol = StringField(1, required=True)
  total_quantity = IntegerField(2, required=True)
  trade_type = EnumField(TradeType, 3, required=True)
  lots = MessageField(Lot, 4, repeated=True)
  limit = IntegerField(5)

# order = Order(symbol='GOOG',
#               total_quantity=10,
#               trade_type=TradeType.BUY)
# lot1 = Lot(price=304,
#            quantity=7)
# lot2 = Lot(price = 305,
#            quantity=3)
# order.lots = [lot1, lot2]
# # Now object is initialized!
# order.check_initialized()