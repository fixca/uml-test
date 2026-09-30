import unittest

from src.class_diagram.uml_attribute import UMLAttribute


class UMLAttributeTest(unittest.TestCase):
    def test_name_is_required(self):
        with self.assertRaises(ValueError):
            UMLAttribute("")

    def test_optional_fields_are_optional(self):
        attr = UMLAttribute("count")
        self.assertEqual(attr.name, "count")
        self.assertIsNone(attr.type)
        self.assertIsNone(attr.access)

    def test_setters_update_values(self):
        attr = UMLAttribute("count", "int", "private")
        attr.type = "float"
        attr.access = "public"

        self.assertEqual(attr.type, "float")
        self.assertEqual(attr.access, "public")


if __name__ == "__main__":
    unittest.main()