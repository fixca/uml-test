from diagram_editor.application.document_session import DocumentSession
from diagram_editor.core.domain.models import ValidationState
from diagram_editor.modules.mermaid.source_sync import SourceSyncError
import pytest


def test_invalid_source_does_not_replace_last_valid_model():
    s = DocumentSession('classDiagram\nclass A\n')
    original = s.document.nodes[0].id
    s.begin_source_edit('classDiagram\nnot valid\n')
    assert s.status == ValidationState.VALIDATING
    assert s.document.nodes[0].id == original
    assert not s.validate(s.source_revision)
    assert s.status == ValidationState.INVALID
    assert s.document.nodes[0].id == original
    assert s.source == 'classDiagram\nnot valid\n'
    with pytest.raises(SourceSyncError):
        s.delete({original})
    s.begin_source_edit('classDiagram\nclass A\nclass B\n')
    assert s.validate(s.source_revision)
    assert len(s.document.nodes) == 2


def test_old_async_result_is_discarded():
    s = DocumentSession('classDiagram\nclass A\n')
    s.begin_source_edit('classDiagram\nclass B\n')
    old_rev = s.source_revision
    s.begin_source_edit('classDiagram\nclass C\n')
    assert not s.validate(old_rev)
    assert s.validate(s.source_revision)
    assert [n.key for n in s.document.nodes] == ['C']


def test_drag_and_undo_redo_keeps_source_and_position():
    s = DocumentSession('classDiagram\nclass A\n')
    source = s.source
    node = s.document.nodes[0]
    s.move_node(node.id, 500, 200)
    assert s.source == source
    assert (s.document.nodes[0].x,s.document.nodes[0].y) == (500,200)
    assert s.undo()
    assert s.validate(s.source_revision)
    assert (s.document.nodes[0].x,s.document.nodes[0].y) != (500,200)
    assert s.redo()
    assert s.validate(s.source_revision)
    assert (s.document.nodes[0].x,s.document.nodes[0].y) == (500,200)


def test_gui_delete_patches_minimally():
    code = 'classDiagram\n%% important comment\nclass A\nclass B\nA --> B\n'
    s = DocumentSession(code)
    selected = {s.document.nodes[1].id}
    s.delete(selected)
    assert '%% important comment' in s.source
    assert 'class A' in s.source
    assert 'class B' not in s.source
    assert '-->' not in s.source


def test_clipboard_paste_new_identity_and_relation():
    s = DocumentSession('classDiagram\nclass A\nclass B\nA --> B\n')
    ids = {n.id for n in s.document.nodes}
    clip = s.copy(ids)
    s.paste(clip)
    assert len(s.document.nodes) == 4
    assert len(s.document.edges) == 2
    assert len({n.id for n in s.document.nodes}) == 4
    assert 'A_copy' in s.source and 'B_copy' in s.source


def test_implicit_participant_reference_delete_refused():
    s = DocumentSession('sequenceDiagram\nA->>B: Hi\n')
    with pytest.raises(SourceSyncError, match='메시지'):
        s.delete({s.document.nodes[0].id})


def test_revisions_monotonic_after_undo():
    s = DocumentSession('classDiagram\nclass A\n')
    s.begin_source_edit('classDiagram\nclass A\nclass B\n')
    assert s.validate(s.source_revision)
    rev = s.source_revision
    assert s.undo()
    assert s.source_revision > rev
    assert s.validate(s.source_revision)


def test_move_changes_edit_revision_not_source_revision():
    s = DocumentSession('classDiagram\nclass A\n')
    source_revision = s.source_revision
    edit_revision = s.edit_revision
    node = s.document.nodes[0]
    s.move_node(node.id, 312, 244)
    assert s.source_revision == source_revision
    assert s.edit_revision == edit_revision + 1
    assert s.status == ValidationState.VALID


def test_sessions_have_isolated_revision_and_history():
    a = DocumentSession('classDiagram\nclass A\n')
    b = DocumentSession('classDiagram\nclass B\n')
    a.begin_source_edit('classDiagram\nclass A\nclass C\n')
    assert a.history.can_undo
    assert not b.history.can_undo
    assert b.source_revision == 0
    assert a.document_id != b.document_id


def test_multi_node_drag_is_one_command():
    s = DocumentSession('classDiagram\nclass A\nclass B\n')
    a, b = s.document.nodes
    start = [(a.x,a.y),(b.x,b.y)]
    s.move_nodes([(a.id, 400, 100), (b.id, 600, 120)])
    assert s.edit_revision == 1
    assert [(n.x,n.y) for n in s.document.nodes] == [(400,100),(600,120)]
    assert s.undo()
    assert s.validate(s.source_revision)
    assert [(n.x,n.y) for n in s.document.nodes] == start
