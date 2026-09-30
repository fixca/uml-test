import unittest

from src.class_diagram.uml_method import UMLMethod


class UMLMethodTest(unittest.TestCase):
    def test_name_is_required(self):
        with self.assertRaises(ValueError):
            UMLMethod("")

    def test_optional_fields_are_optional(self):
        method = UMLMethod("getName")
        self.assertEqual(method.name, "getName")
        self.assertIsNone(method.type)
        self.assertEqual(method.parameters, [])
        self.assertIsNone(method.access)

    def test_setters_update_values(self):
        method = UMLMethod("sum", "int", ["int a", "int b"], "public")
        method.type = "float"
        method.parameters = ["float x", "float y"]
        method.access = "private"

        self.assertEqual(method.type, "float")
        self.assertEqual(method.parameters, ["float x", "float y"])
        self.assertEqual(method.access, "private")


if __name__ == "__main__":
    unittest.main()