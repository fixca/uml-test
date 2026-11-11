class SequenceObject:
    def __init__(self, name):
        self.__name = name

    @property
    def name(self):
        return self.__name


class ActorObject(SequenceObject):
    pass


objQueue = []

def addObject(obj):
    if not isinstance(obj, SequenceObject):
        raise TypeError("obj must be an instance of SequenceObject")
    if obj in objQueue:
        raise ValueError("obj is already in the queue")
    objQueue.append(obj)

def removeObject(obj):
    if not isinstance(obj, SequenceObject):
        raise TypeError("obj must be an instance of SequenceObject")
    if obj not in objQueue:
        raise ValueError("obj is not in the queue")
    objQueue.remove(obj)

