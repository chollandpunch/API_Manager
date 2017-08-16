from core.base.core_message import *

def getUserIP():
  return 'hollandc', '192.168.0.1'

class User(Message):
  first_name = StringField(1)
  last_name = StringField(2, required=True)
  ldap =