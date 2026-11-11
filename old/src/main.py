"""
Main entry point for the application.
"""

from src.class_diagram.coupler import couplers, generateCouple
from src.class_diagram.uml_class import UMLClass
from src.class_diagram.uml_attribute import UMLAttribute
from src.class_diagram.uml_method import UMLMethod

# from src.sequence_diagram.sequence_active_box import SequenceActiveBox, activeBoxQueue, addActiveBox, removeActiveBox
# from src.sequence_diagram.sequence_message import SequenceMessage, addMessage, removeMessage, messageQueue
# from src.sequence_diagram.sequence_object import SequenceObject, addObject, objQueue, removeObject

# def main():

    # sequenceObjA = SequenceObject("A")
    # sequenceObjB = SequenceObject("B")

    # # addObject(sequenceObjA)
    # # addObject(sequenceObjB)

    # msgA = SequenceMessage(sequenceObjA, sequenceObjB, "Hello")
    # msgB = SequenceMessage(sequenceObjB, sequenceObjA, "Hi")

    # # addMessage(msgA) 
    # # addMessage(msgB)
    
    # atvBox = SequenceActiveBox(msgA, msgB)
    # # addActiveBox(atvBox)

    # for obj in objQueue:
    #     print(f"{obj.name}\t", end="")

    # for i in range(6):

    #     msg = messageQueue[i]

    #     if msg == None:
    #         print(f"|\t|\t", end="")


    #     print(f"\n{messageQueue[i].startObj.name} -> {messageQueue[i].endObj.name}: {messageQueue[i].message}")




    
    
    



def main():
    # """Main function."""
    # testAClass = UMLClass("TestA")
    # testAClass.add_attribute(UMLAttribute("testA", "String", "private"))    

    # testBClass = UMLClass("TestB")
    # testBClass.add_attribute(UMLAttribute("testB", "String", "private"))

    couplers.clear()
    # generateCouple(testAClass, testBClass)

    # for coupler in couplers:
    #     print(f"Coupler: {coupler.objA.name} <-> {coupler.objB.name}")

    ceoClass = UMLClass("CEO")
    ceoClass.add_attribute(UMLAttribute("Login", "String", "public"))
    ceoClass.add_attribute(UMLAttribute("Password", "String", "public"))

    projectClass = UMLClass("Project")
    projectClass.add_attribute(UMLAttribute("ID", "Number", "public"))
    projectClass.add_attribute(UMLAttribute("Name", "String", "public"))
    projectClass.add_attribute(UMLAttribute("TasksId", "Number[]", "public"))
    projectClass.add_attribute(UMLAttribute("Access", "Number[]", "public"))

    reportClass = UMLClass("Report")
    reportClass.add_attribute(UMLAttribute("Time", "Number", "public"))
    reportClass.add_attribute(UMLAttribute("Date", "Date", "public"))
    reportClass.add_attribute(UMLAttribute("Project", "String", "public"))
    reportClass.add_attribute(UMLAttribute("Task", "String", "public"))

    employeeClass = UMLClass("Employee")
    employeeClass.add_attribute(UMLAttribute("ID", "Number", "public"))
    employeeClass.add_attribute(UMLAttribute("Login", "String", "public"))
    employeeClass.add_attribute(UMLAttribute("Password", "String", "public"))

    ceoProjectCoupler = generateCouple(ceoClass, projectClass, "Manages")
    ceoReportCoupler = generateCouple(ceoClass, reportClass, "Controls")
    ceoEmployeeCoupler = generateCouple(ceoClass, employeeClass, "Assigns")

    # print(ceoClass)
    # print(projectClass)
    # print(reportClass)

    for coupler in couplers:
        # print(f"Coupler: {coupler.objA} <-> {coupler.objB}, Relation: {coupler.relationalName}, type: {coupler.relationType}")
        print(f"Coupler: {coupler.objA.name} <-> {coupler.objB.name}, Relation: {coupler.relationalName}, type: {coupler.relationType}")

    



    # uml_class = UMLClass("Person")
    # uml_class.add_attribute(UMLAttribute("name", "String", "private"))
    # uml_class.add_attribute(UMLAttribute("age", "int", "private"))
    # uml_class.add_method(UMLMethod("getName", "String", [], "public"))
    # uml_class.add_method(UMLMethod("getAge", "int", [], "public"))

    # print(f"Class: {uml_class.name}")
    # for attr in uml_class.attributes:
    #     print(f"Attribute: {attr.name}, Type: {attr.type}, Access: {attr.access}")
    # for method in uml_class.methods:
    #     print(f"Method: {method.name}, Type: {method.type}, Access: {method.access}")


if __name__ == "__main__":
    main()
