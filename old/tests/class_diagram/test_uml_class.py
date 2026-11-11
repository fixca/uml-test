import unittest

from src.class_diagram.uml_attribute import UMLAttribute
from src.class_diagram.uml_class import UMLClass
from src.class_diagram.uml_method import UMLMethod


class UMLClassTest(unittest.TestCase):
    def test_name_is_read_only(self):
        uml_class = UMLClass("Person")
        with self.assertRaises(AttributeError):
            uml_class.name = "Student"

    def test_add_and_remove_attribute(self):
        uml_class = UMLClass("Person")
        attr = UMLAttribute("name", "String", "private")

        uml_class.add_attribute(attr)
        self.assertEqual(len(uml_class.attributes), 1)
        self.assertEqual(uml_class.attributes[0].name, "name")

        uml_class.remove_attribute(attr)
        self.assertEqual(uml_class.attributes, [])

    def test_add_and_remove_method(self):
        uml_class = UMLClass("Person")
        method = UMLMethod("getName", "String", [], "public")

        uml_class.add_method(method)
        self.assertEqual(len(uml_class.methods), 1)
        self.assertEqual(uml_class.methods[0].name, "getName")

        uml_class.remove_method(method)
        self.assertEqual(uml_class.methods, [])

    def test_add_attribute_type_validation(self):
        uml_class = UMLClass("Person")
        with self.assertRaises(TypeError):
            uml_class.add_attribute("not an attribute")

    def test_remove_attribute_type_validation(self):
        uml_class = UMLClass("Person")
        with self.assertRaises(TypeError):
            uml_class.remove_attribute("not an attribute")

    def test_add_method_type_validation(self):
        uml_class = UMLClass("Person")
        with self.assertRaises(TypeError):
            uml_class.add_method("not a method")

    def test_remove_method_type_validation(self):
        uml_class = UMLClass("Person")
        with self.assertRaises(TypeError):
            uml_class.remove_method("not a method")


if __name__ == "__main__":
    unittest.main()