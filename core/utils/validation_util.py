import re

def valid_domain(domain):
  pattern = r'^(([a-zA-Z]{1})|([a-zA-Z]{1}[a-zA-Z]{1})|([a-zA-Z]{1}[0-9]{1})|([0-9]{1}[a-zA-Z]{1})|([a-zA-Z0-9][a-zA-Z0-9-_]{1,61}[a-zA-Z0-9]))\.([a-zA-Z]{2,6}|[a-zA-Z0-9-]{2,30}\.[a-zA-Z]{2,3})$'
  match = re.match(pattern, domain)
  return  match is not None, match

def valid_email_localpart(name):

  def rule_length_and_type(name):
    return isinstance(name, basestring) and len(name) <=63

  def rule_dots(name):
    return all([not name.startswith('.'),
                not name.endswith('.'),
                name.find('..') == -1])

  def rule_all_characters(name):
    pattern = r"[\w!$%^&*{}#+-=?_~`|']{" + str(len(name)) +"}"
    return re.match(pattern, name) is not None

  rules = [rule_all_characters,
           rule_dots,
           rule_length_and_type]


  return all(map(lambda x: x(name), rules))


def valid_email(email):
  if isinstance(email, basestring) and '@' in email:
    parts = email.split('@')
    if len(parts) == 2:
      return valid_email_localpart(parts[0]), valid_domain(parts[1])[0]
    else:
      return None, len(parts)
  else:
    return None, None

