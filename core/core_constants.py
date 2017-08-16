# Attributes that are reserved by a class definition that
# may not be used by either Enum or Message class definitions.
_RESERVED_ATTRIBUTE_NAMES = frozenset(
    ['__module__', '__doc__', '__qualname__'])

_POST_INIT_FIELD_ATTRIBUTE_NAMES = frozenset(
    ['name',
     '_message_definition',
     '_MessageField__type',
     '_EnumField__type',
     '_EnumField__resolved_default'])

_POST_INIT_ATTRIBUTE_NAMES = frozenset(
    ['_message_definition', '_DEFAULT'])

# Maximum enumeration value as defined by the protocol buffers standard.
# All enum values must be less than or equal to this value.
MAX_ENUM_VALUE = (2 ** 29) - 1

# Maximum field number as defined by the protocol buffers standard.
# All field numbers must be less than or equal to this value.
MAX_FIELD_NUMBER = (2 ** 29) - 1

# Field numbers between 19000 and 19999 inclusive are reserved by the
# protobuf protocol and may not be used by fields.
FIRST_RESERVED_FIELD_NUMBER = 19000
LAST_RESERVED_FIELD_NUMBER = 19999

# URL_HEADER is used for web calls (data_import)
URL_HEADER = {'User-Agent': 'Mozilla/5.0'}