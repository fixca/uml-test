class UMLMethod:
    def __init__(self, name, type=None, parameters=None, access=None):
        if not name:
            raise ValueError("name is required")
        self.__name = name
        self.__type = type
        self.__parameters = parameters if parameters is not None else []
        self.__access = access

    @property
    def name(self):
        return self.__name

    @property
    def type(self):
        return self.__type

    @type.setter
    def type(self, type):
        self.__type = type

    @property
    def parameters(self):
        return self.__parameters

    @parameters.setter
    def parameters(self, parameters):
        self.__parameters = parameters

    @property
    def access(self):
        return self.__access

    @access.setter
    def access(self, access):
        self.__access = access

    def toString(self):
        return f"UMLMethod(name={self.name!r}, type={self.type!r}, parameters={self.parameters!r}, access={self.access!r})"

    def __str__(self):
        return self.toString()

    def __repr__(self):
        return self.toString()