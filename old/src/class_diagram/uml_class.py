from src.class_diagram.uml_attribute import UMLAttribute
from src.class_diagram.uml_method import UMLMethod


class UMLClass:
    def __init__(self, name):
        self.__name = name
        self.__attributes = []
        self.__methods = []

    @property
    def name(self):
        return self.__name

    @property
    def attributes(self):
        return self.__attributes

    @property
    def methods(self):
        return self.__methods

    def add_attribute(self, attribute):
        if not isinstance(attribute, UMLAttribute):
            raise TypeError("attribute must be an instance of UMLAttribute")
        self.__attributes.append(attribute)

    def remove_attribute(self, attribute):
        if not isinstance(attribute, UMLAttribute):
            raise TypeError("attribute must be an instance of UMLAttribute")
        self.__attributes.remove(attribute)

    def add_method(self, method):
        if not isinstance(method, UMLMethod):
            raise TypeError("method must be an instance of UMLMethod")
        self.__methods.append(method)

    def remove_method(self, method):
        if not isinstance(method, UMLMethod):
            raise TypeError("method must be an instance of UMLMethod")
        self.__methods.remove(method)

    def toString(self):
        return f"UMLClass(name={self.name!r}, attributes={self.attributes!r}, methods={self.methods!r})"

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return self.toString()