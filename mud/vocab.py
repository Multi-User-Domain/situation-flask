from enum import Enum

#
#   This class contains constants for semantic types referenced in the application
#


# NOTE: when upgrading to Python 3.11, these classes can instead inherit the built-in class StrEnum
class StrEnum(str, Enum):
    """
    An Enum suitable for Python < 3.11 to implement StrEnum
    """

    def __str__(self) -> str:
        return self.value


class MUD_ACCT(StrEnum):
    Account = "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudacct.ttl#Account"


class MUD_CHAR(StrEnum):
    Character = "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudchar.ttl#Character"


class MUD_DIALOGUE(StrEnum):
    Interaction = "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/muddialogue.ttl#Interaction"

class MUD_WORLD(StrEnum):
    Region = "https://raw.githubusercontent.com/Multi-User-Domain/vocab/main/mudworld.ttl#Region"
