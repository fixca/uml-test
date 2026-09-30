from enum import Enum


class RelationType(Enum):
    ASSCIATION = "ASSCIATION"
    GENERALIZATION = "GENERALIZATION"
    AGGREGATION = "AGGREGATION"
    COMPOSITION = "COMPOSITION"
    DEPENDENCY = "DEPENDENCY"
    REALIZATION = "REALIZATION"


class Coupler:
    def __init__(self, objA, objB, relationalName=None, relationType=RelationType.ASSCIATION):
        from src.class_diagram.uml_class import UMLClass

        if objA is None:
            raise ValueError("objA is required")
        if objB is None:
            raise ValueError("objB is required")
        if not isinstance(objA, UMLClass):
            raise TypeError("objA must be an instance of UMLClass")
        if not isinstance(objB, UMLClass):
            raise TypeError("objB must be an instance of UMLClass")
        if relationalName is not None and not isinstance(relationalName, str):
            raise TypeError("relationalName must be a string")
        if relationType is not None and not isinstance(relationType, RelationType):
            raise TypeError("relationType must be an instance of RelationType")

        self.__objA = objA
        self.__objB = objB
        self.__relationalName = relationalName
        self.__relationType = relationType

    @property
    def objA(self):
        return self.__objA

    @property
    def objB(self):
        return self.__objB

    @property
    def relationalName(self):
        return self.__relationalName

    @relationalName.setter
    def relationalName(self, relationalName):
        if not isinstance(relationalName, str):
            raise TypeError("relationalName must be a string")
        self.__relationalName = relationalName

    @property
    def relationType(self):
        return self.__relationType

    @relationType.setter
    def relationType(self, relationType):
        if not isinstance(relationType, RelationType):
            raise TypeError("relationType must be an instance of RelationType")
        self.__relationType = relationType


couplers = []


def generateCouple(
    objA,
    objB,
    relationalName=None,
    relationType=RelationType.ASSCIATION,
):
    from src.class_diagram.uml_class import UMLClass

    if objA is None:
        raise ValueError("objA is required")
    if objB is None:
        raise ValueError("objB is required")
    if not isinstance(objA, UMLClass):
        raise TypeError("objA must be an instance of UMLClass")
    if not isinstance(objB, UMLClass):
        raise TypeError("objB must be an instance of UMLClass")

    coupler = Coupler(objA, objB, relationalName, relationType)
    couplers.append(coupler)
    return coupler
