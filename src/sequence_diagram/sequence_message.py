from src.sequence_diagram.sequence_object import SequenceObject


class SequenceMessage:
    def __init__(self, startObj, endObj, message):
        if not isinstance(startObj, SequenceObject):
            raise TypeError("startObj must be an instance of SequenceObject")
        if not isinstance(endObj, SequenceObject):
            raise TypeError("endObj must be an instance of SequenceObject")
        self.__startObj = startObj
        self.__endObj = endObj
        self.__message = message

    @property
    def startObj(self):
        return self.__startObj

    @property
    def endObj(self):
        return self.__endObj

    @property
    def message(self):
        return self.__message


messageQueue = []


def addMessage(obj):
    if not isinstance(obj, SequenceMessage):
        raise TypeError("obj must be an instance of SequenceMessage")
    messageQueue.append(obj)


def removeMessage(obj):
    if not isinstance(obj, SequenceMessage):
        raise TypeError("obj must be an instance of SequenceMessage")
    for index, queued_message in enumerate(messageQueue):
        if queued_message is obj:
            messageQueue.pop(index)
            return
    raise ValueError("obj is not in the message queue")
