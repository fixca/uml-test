"""Composition root registry for non-Qt components."""
from dataclasses import dataclass
from diagram_editor.modules.mermaid.parser import SubsetMermaidParser
from diagram_editor.modules.diagram_types.registry import TypeRegistry
from diagram_editor.modules.persistence.repository import ProjectRepository, RecoveryRepository
from diagram_editor.modules.events.bus import EventBus


@dataclass
class CoreServices:
    parser: SubsetMermaidParser
    diagram_types: TypeRegistry
    project_repository: ProjectRepository
    recovery_repository: RecoveryRepository
    event_bus: EventBus


def create_services() -> CoreServices:
    return CoreServices(SubsetMermaidParser(), TypeRegistry(), ProjectRepository(), RecoveryRepository(), EventBus())
