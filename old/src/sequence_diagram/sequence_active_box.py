from src.sequence_diagram.sequence_message import SequenceMessage


class SequenceActiveBox:
    def __init__(self, startObj, endObj):
        if not isinstance(startObj, SequenceMessage):
            raise TypeError("startObj must be an instance of SequenceMessage")
        if not isinstance(endObj, SequenceMessage):
            raise TypeError("endObj must be an instance of SequenceMessage")
        self.__startObj = startObj
        self.__endObj = endObj

    @property
    def startObj(self):
        return self.__startObj

    @property
    def endObj(self):
        return self.__endObj


activeBoxQueue = []


def addActiveBox(obj):
    if not isinstance(obj, SequenceActiveBox):
        raise TypeError("obj must be an instance of SequenceActiveBox")
    activeBoxQueue.append(obj)


def removeActiveBox(obj):
    if not isinstance(obj, SequenceActiveBox):
        raise TypeError("obj must be an instance of SequenceActiveBox")
    for index, queued_box in enumerate(activeBoxQueue):
        if queued_box is obj:
            activeBoxQueue.pop(index)
            return
    raise ValueError("obj is not in the active box queue")
