import unittest

from src.sequence_diagram import ActorObject, SequenceMessage, SequenceObject, addMessage, removeMessage
from src.sequence_diagram.sequence_message import messageQueue


class SequenceMessageTest(unittest.TestCase):
    def setUp(self):
        messageQueue.clear()

    def test_sequence_message_stores_objects_and_message(self):
        start_object = ActorObject("User")
        end_object = SequenceObject("System")

        sequence_message = SequenceMessage(start_object, end_object, "login")

        self.assertIs(sequence_message.startObj, start_object)
        self.assertIs(sequence_message.endObj, end_object)
        self.assertEqual(sequence_message.message, "login")

    def test_add_message_pushes_to_queue(self):
        message = SequenceMessage(ActorObject("User"), SequenceObject("System"), "login")

        addMessage(message)

        self.assertEqual(messageQueue, [message])

    def test_remove_message_removes_by_identity(self):
        message = SequenceMessage(ActorObject("User"), SequenceObject("System"), "login")
        message_with_same_values = SequenceMessage(message.startObj, message.endObj, message.message)
        addMessage(message)

        with self.assertRaises(ValueError):
            removeMessage(message_with_same_values)

        removeMessage(message)
        self.assertEqual(messageQueue, [])


if __name__ == "__main__":
    unittest.main()
