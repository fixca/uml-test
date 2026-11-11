import io
import zipfile
import pytest
from pathlib import Path
from diagram_editor.application.document_session import DocumentSession
from diagram_editor.modules.persistence.archive_codec import ArchiveError, decode, encode, read_archive, write_atomic
from diagram_editor.modules.persistence.repository import RecoveryRepository


def test_zip_roundtrip_keeps_source_invalid_and_last_good(tmp_path):
    s = DocumentSession('classDiagram\nclass A\n')
    s.move_node(s.document.nodes[0].id, 700, 210)
    s.begin_source_edit('classDiagram\nthis is invalid\n')
    s.validate(s.source_revision)
    dest = tmp_path/'project.dgmzip'
    write_atomic(dest, s.snapshot())
    recovered = read_archive(dest)
    assert recovered.source.endswith('invalid\n')
    assert recovered.document.nodes[0].x == 700
    assert recovered.status == 'INVALID'


def test_recovery_does_not_change_manual_project(tmp_path):
    s = DocumentSession('classDiagram\nclass A\n')
    project = tmp_path/'project.dgmzip'
    write_atomic(project, s.snapshot())
    before = project.read_bytes()
    s.begin_source_edit('classDiagram\nclass A\n%% comment edit\n')
    r = RecoveryRepository(tmp_path/'recovery')
    r.save(s.snapshot())
    assert project.read_bytes() == before
    assert r.candidates(s.document_id)[0][1].source.endswith('%% comment edit\n')


def test_zip_traversal_rejected():
    payload = io.BytesIO()
    with zipfile.ZipFile(payload,'w') as z:
        z.writestr('../evil.txt', 'evil')
        z.writestr('manifest.json', '{}')
    with pytest.raises(ArchiveError):
        decode(payload.getvalue())


def test_duplicate_zip_entry_rejected():
    payload = io.BytesIO()
    with zipfile.ZipFile(payload,'w') as z:
        z.writestr('manifest.json', '{}')
        z.writestr('manifest.json', '{}')
        z.writestr('document.json', '{}')
        z.writestr('source.mmd', '')
    with pytest.raises(ArchiveError):
        decode(payload.getvalue())


def test_checksum_tamper_rejected():
    s = DocumentSession('classDiagram\nclass A\n')
    original = encode(s.snapshot())
    inp = zipfile.ZipFile(io.BytesIO(original))
    payload = io.BytesIO()
    with zipfile.ZipFile(payload,'w') as z:
        for name in inp.namelist():
            data = inp.read(name)
            if name == 'source.mmd': data = b'classDiagram\nclass B\n'
            z.writestr(name,data)
    with pytest.raises(ArchiveError,match='체크섬'):
        decode(payload.getvalue())


def test_cancel_does_not_replace_valid_zip(tmp_path):
    from threading import Event
    from diagram_editor.modules.persistence.archive_codec import SaveCancelled
    dest = tmp_path/'p.dgmzip'
    s = DocumentSession('classDiagram\nclass A\n')
    write_atomic(dest, s.snapshot())
    original = dest.read_bytes()
    cancel = Event(); cancel.set()
    s.begin_source_edit('classDiagram\nclass B\n')
    with pytest.raises(SaveCancelled):
        write_atomic(dest,s.snapshot(),cancel)
    assert dest.read_bytes() == original


def test_recovery_rotation_keeps_most_recent(tmp_path):
    r = RecoveryRepository(tmp_path/'recovery',keep=2)
    s = DocumentSession('classDiagram\nclass A\n')
    for i in range(4):
        s.begin_source_edit(f'classDiagram\nclass A\n%% revision {i}\n')
        r.save(s.snapshot())
    result = r.candidates(s.document_id)
    assert len(result) == 2
    assert result[0][1].source.endswith('revision 3\n')
