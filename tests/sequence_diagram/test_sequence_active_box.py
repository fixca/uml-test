import unittest

from src.sequence_diagram import ActorObject, SequenceActiveBox, SequenceMessage, SequenceObject, activeBoxQueue, addActiveBox, removeActiveBox


class SequenceActiveBoxTest(unittest.TestCase):
    def setUp(self):
        activeBoxQueue.clear()

    def test_sequence_active_box_stores_messages(self):
        start_message = SequenceMessage(ActorObject("User"), SequenceObject("System"), "start")
        end_message = SequenceMessage(ActorObject("User"), SequenceObject("System"), "end")

        active_box = SequenceActiveBox(start_message, end_message)

        self.assertIs(active_box.startObj, start_message)
        self.assertIs(active_box.endObj, end_message)

    def test_active_box_queue_add_and_remove_by_identity(self):
        active_box = SequenceActiveBox(
            SequenceMessage(ActorObject("User"), SequenceObject("System"), "start"),
            SequenceMessage(ActorObject("User"), SequenceObject("System"), "end"),
        )
        addActiveBox(active_box)

        removeActiveBox(active_box)

        self.assertEqual(activeBoxQueue, [])


if __name__ == "__main__":
    unittest.main()
