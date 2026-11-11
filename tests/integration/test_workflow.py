from diagram_editor.application.document_session import DocumentSession
from diagram_editor.modules.persistence.repository import ProjectRepository, RecoveryRepository


def test_class_parse_move_edit_export_model_persist_reopen(tmp_path):
    s = DocumentSession('classDiagram\nclass A\nclass B\nA --> B : uses\n')
    a = s.document.nodes[0]
    s.move_node(a.id, 600, 120)
    s.begin_source_edit(s.source + '%% Changed only the comment\n')
    s.validate(s.source_revision)
    assert s.document.nodes[0].x == 600
    path = str(tmp_path/'main.dgmzip')
    repo = ProjectRepository()
    repo.save(path, s.snapshot())
    loaded = DocumentSession.from_snapshot(repo.load(path))
    assert loaded.document.nodes[0].x == 600
    assert loaded.document.nodes[0].id == a.id
    assert loaded.source.endswith('%% Changed only the comment\n')


def test_sequence_delete_and_copy_preserve_order():
    s = DocumentSession('sequenceDiagram\nparticipant A\nparticipant B\nA->>B: First\nB-->>A: Second\n')
    second = s.document.edges[1].id
    clip = s.copy({second})
    s.delete({second})
    assert [e.label for e in s.document.edges] == ['First']
    s.paste(clip)
    assert [e.label for e in s.document.edges] == ['First','Second']
