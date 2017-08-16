import inspect
from core_error import *

def _lateimportMessage():
  from core.base import core_message as cm
  return cm.Message, cm.MessageField


def _lateimportField():
  from core.base import core_field as cf
  return cf.StringField, cf.IntegerField


def listChildren(obj):
  """Recursively find all children of obj."""
  child_list=[]

  if inspect.isclass(obj):
    for child in obj.__subclasses__():
      child_list.append(child)
      for gchild in listChildren(child):
        child_list.append(gchild)


  return child_list

Message, MessageField = _lateimportMessage()
StringField, IntegerField = _lateimportField()

class ExceptionField(StringField):
   def validate_element(self, value):

     nameformat = lambda o: '.'.join([x.__name__ for x in list(
       reversed(inspect.getmro(o))) if issubclass(x, Error)])

     validation_error = ValidationError('Field encountered undefined Error: %r' % (value))

     if inspect.isclass(value) and issubclass(value, Exception):
        if value in listChildren(Error):
          value = nameformat(value)
        else:
          raise validation_error
     elif isinstance(value, str):
       childlist = listChildren(Error)
       childnames = [x.__name__ for x in childlist]
       try:
         value = nameformat(childlist[childnames.index(value)])
       except ValueError, e:
         raise validation_error, e

     if super(ExceptionField, self).validate_element(value):
       return value

class MsgKey(Message):
  key = StringField(1, required=True)
  message = StringField(2, required=True)
  exception = ExceptionField(3, default=None)

class LocalKey(Message):
  desc = StringField(2)
  location = StringField(3)
  messages = MessageField(MsgKey, 4, repeated=True)

def msgkey(key, value, exception=None):
  return MsgKey(key=key, message=value, exception=exception)


def localkey(key, desc=None, location=None, messages=None):
  return LocalKey(key=key, desc=desc, location=location, messages=messages)

__all__ = ['localkey', 'msgkey', 'LocalKey', 'MsgKey', 'listChildren']
