import pytest
from diagram_editor.modules.mermaid.parser import SubsetMermaidParser, ParseError


def test_class_diagram_relations_members_and_layout():
    p = SubsetMermaidParser()
    src = 'classDiagram\nclass Alpha {\n  +String name\n  +run()\n}\nclass Beta\nAlpha --> Beta : use\n'
    doc = p.parse(src)
    assert doc.diagram_type == 'class'
    assert len(doc.nodes) == 2 and len(doc.edges) == 1
    assert doc.nodes[0].members == ['+String name', '+run()']
    assert doc.nodes[0].height > 72
    assert doc.edges[0].label == 'use'


def test_sequence_message_order():
    p = SubsetMermaidParser()
    doc = p.parse('sequenceDiagram\nparticipant A as Alice\nparticipant B\nA->>B: One\nB-->>A: Two\n')
    assert len(doc.nodes) == 2
    assert [e.order for e in doc.edges] == [0,1]
    assert [e.label for e in doc.edges] == ['One','Two']
    assert doc.nodes[0].label == 'Alice'


def test_preserves_ids_and_moved_positions_on_source_reparse():
    p = SubsetMermaidParser()
    a = p.parse('classDiagram\nclass A\nclass B\nA --> B\n')
    a.nodes[0].x = 777
    b = p.parse('classDiagram\n%% comment\nclass A\nclass B\nA --> B\n', a)
    assert a.nodes[0].id == b.nodes[0].id
    assert b.nodes[0].x == 777
    assert a.edges[0].id == b.edges[0].id


def test_invalid_input_raises_with_line_number():
    with pytest.raises(ParseError, match='2행'):
        SubsetMermaidParser().parse('classDiagram\nNO MERMAID COMMAND')


def test_unclosed_block_is_error():
    with pytest.raises(ParseError, match='닫는'):
        SubsetMermaidParser().parse('classDiagram\nclass X {\n +a\n')


def test_sequence_groups_and_notes():
    source = 'sequenceDiagram\nparticipant A\nparticipant B\nloop Retry\nA->>B: hello\nNote right of B: log\nend\n'
    doc = SubsetMermaidParser().parse(source)
    assert [d['kind'] for d in doc.decorations] == ['block_start','note','block_end']
