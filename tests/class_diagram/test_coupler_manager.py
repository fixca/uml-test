import unittest

from src.class_diagram.coupler import Coupler, RelationType
from src.class_diagram.coupler import couplers, generateCouple
from src.class_diagram.uml_class import UMLClass


class CouplerManagerTest(unittest.TestCase):
    def setUp(self):
        couplers.clear()  # Clear the couplers list before each test

    def test_generate_couple_success(self):
        class_a = UMLClass("A")
        class_b = UMLClass("B")

        couple = generateCouple(class_a, class_b)

        self.assertIsInstance(couple, Coupler)
        self.assertEqual(len(couplers), 1)
        self.assertEqual(couplers[0], couple)
        self.assertEqual(couple.objA.name, "A")
        self.assertEqual(couple.objB.name, "B")
        self.assertEqual(couple.relationType, RelationType.ASSCIATION)

    def test_generate_couple_accepts_relation_metadata(self):
        couple = generateCouple(
            UMLClass("A"),
            UMLClass("B"),
            "inherits from",
            RelationType.GENERALIZATION,
        )

        self.assertEqual(couple.relationalName, "inherits from")
        self.assertEqual(couple.relationType, RelationType.GENERALIZATION)

    def test_generate_couple_rejects_invalid_relation_metadata(self):
        with self.assertRaises(TypeError):
            generateCouple(UMLClass("A"), UMLClass("B"), relationType="association")

        with self.assertRaises(TypeError):
            generateCouple(UMLClass("A"), UMLClass("B"), relationalName=123)

    def test_generate_couple_rejects_non_uml_class_obj_a(self):
        with self.assertRaises(TypeError):
            generateCouple("not a class", UMLClass("B"))

    def test_generate_couple_rejects_non_uml_class_obj_b(self):
        with self.assertRaises(TypeError):
            generateCouple(UMLClass("A"), "not a class")


if __name__ == "__main__":
    unittest.main()