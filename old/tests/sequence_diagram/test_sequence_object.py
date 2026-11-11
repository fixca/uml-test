import unittest

from src.sequence_diagram import ActorObject, SequenceObject, addObject, objQueue, removeObject


class SequenceObjectTest(unittest.TestCase):
    def setUp(self):
        objQueue.clear()

    def test_name_getter(self):
        entity = SequenceObject("User")

        self.assertEqual(entity.name, "User")

    def test_name_is_read_only(self):
        entity = SequenceObject("User")

        with self.assertRaises(AttributeError):
            entity.name = "Admin"

    def test_add_object_pushes_to_queue(self):
        entity = ActorObject("User")

        addObject(entity)

        self.assertEqual(objQueue, [entity])

    def test_add_object_rejects_invalid_object(self):
        with self.assertRaises(TypeError):
            addObject("User")

    def test_add_object_rejects_duplicate_object(self):
        entity = ActorObject("User")
        addObject(entity)

        with self.assertRaises(ValueError):
            addObject(entity)

    def test_remove_object_removes_from_queue(self):
        entity = ActorObject("User")
        addObject(entity)

        removeObject(entity)

        self.assertEqual(objQueue, [])

    def test_remove_object_rejects_object_not_in_queue(self):
        with self.assertRaises(ValueError):
            removeObject(SequenceObject("User"))


if __name__ == "__main__":
    unittest.main()
