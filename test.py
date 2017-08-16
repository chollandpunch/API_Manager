import core.base.core_enum as cenum
import core.base.core_field as cfield
import core.base.core_message as cmessage

class TradeType(cenum.Enum):
  BUY = 1
  SELL = 2
  SHORT = 3
  CALL = 4

class Lot(cmessage.Message):
  price = cfield.IntegerField(1, required=True)
  quantity = cfield.IntegerField(2, required=True)

class Order(cmessage.Message):
    symbol = cfield.StringField(1, required=True)
    total_quantity = cfield.IntegerField(2, required=True)
    trade_type = cmessage.EnumField(TradeType, 3, required=True)
    lots = cmessage.MessageField(Lot, 4, repeated=True)
    limit = cfield.IntegerField(5)
