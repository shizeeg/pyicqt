# This is a quick implementation of a bool class for Python 2.2.
# It was directly copied from http://www.python.org/peps/pep-0285.html

class bool(int):
    def __new__(cls, val=0):
        # This constructor always returns an existing instance
        if val:
            return True
        else:
            return False

    def __repr__(self):
        if self:
            return "True"
        else:
            return "False"

    __str__ = __repr__

    def __and__(self, other):
        if isinstance(other, bool):
            return bool(int(self) & int(other))
        else:
            return int.__and__(self, other)

    __rand__ = __and__

    def __or__(self, other):
        if isinstance(other, bool):
            return bool(int(self) | int(other))
        else:
            return int.__or__(self, other)

    __ror__ = __or__

    def __xor__(self, other):
        if isinstance(other, bool):
            return bool(int(self) ^ int(other))
        else:
            return int.__xor__(self, other)

    __rxor__ = __xor__

# Bootstrap truth values through sheer willpower
False = int.__new__(bool, 0)
True = int.__new__(bool, 1)
