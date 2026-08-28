"""
Kiểm thử kho tệp cục bộ (TASK-004)

Dùng tmp_path (fixture pytest có sẵn) làm base_path cho LocalFileStorage — KHÔNG
đụng thư mục data/ thật của dự án. Mọi ca đều chỉ thao tác trên hệ thống tệp
tạm của pytest.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.adapters.storage_local import LocalFileStorage


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_init_creates_missing_base_path(tmp_path: Path):
    base = tmp_path / "chua" / "ton" / "tai"
    LocalFileStorage(base)  # side-effect: tạo thư mục
    assert base.is_dir()


def test_save_then_open_returns_same_bytes(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    data = b"hoa-don-dien-tu-mau-xanh"
    ref = storage.save(data, "invoice.jpg")
    assert ref.sha256 == _sha256(data)
    assert ref.size_bytes == len(data)
    with storage.open(ref) as f:
        assert f.read() == data


def test_save_same_content_dedup_single_physical_file(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    data = b"cung-noi-dung-dung-mot-lan"
    ref1 = storage.save(data, "invoice_a.pdf")
    ref2 = storage.save(data, "invoice_b.pdf")  # khác tên, cùng bytes, cùng đuôi
    assert ref1.sha256 == ref2.sha256
    assert ref1.path == ref2.path
    assert ref2 == ref1
    leaf_dir = tmp_path / ref1.sha256[:2] / ref1.sha256[2:4]
    assert len(list(leaf_dir.iterdir())) == 1  # chỉ 1 tệp vật lý
    with storage.open(ref1) as f:
        assert f.read() == data


def test_save_different_content_two_files(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    ref1 = storage.save(b"noi-dung-so-mot", "a.txt")
    ref2 = storage.save(b"noi-dung-so-hai", "b.txt")
    assert ref1.sha256 != ref2.sha256
    assert ref1.path != ref2.path
    with storage.open(ref1) as f:
        assert f.read() == b"noi-dung-so-mot"
    with storage.open(ref2) as f:
        assert f.read() == b"noi-dung-so-hai"


def test_exists_returns_true_after_save_and_false_for_unknown(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    ref = storage.save(b"co-trong-kho", "doc.pdf")
    assert storage.exists(ref.sha256) is True
    assert storage.exists(_sha256(b"chua-bao-gio-duoc-luu")) is False


def test_delete_removes_and_second_delete_is_idempotent(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    ref = storage.save(b"se-bi-xoa", "doc.pdf")
    assert storage.exists(ref.sha256) is True
    storage.delete(ref)
    assert storage.exists(ref.sha256) is False
    storage.delete(ref)  # lần 2 trên ref đã xoá — không được raise lỗi


def test_directory_structure_matches_sha_prefix(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    data = b"cau-truc-thu-muc"
    ref = storage.save(data, "doc.pdf")
    expected_rel = f"{ref.sha256[:2]}/{ref.sha256[2:4]}/{ref.sha256}.pdf"
    assert ref.path == expected_rel
    assert (tmp_path / expected_rel).is_file()
    with (tmp_path / expected_rel).open("rb") as f:
        assert f.read() == data


def test_save_without_extension_stores_bare_name(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    ref = storage.save(b"khong-co-duoi-mo-rong", "noext")
    assert ref.path == f"{ref.sha256[:2]}/{ref.sha256[2:4]}/{ref.sha256}"
    assert ref.content_type is None
    assert storage.exists(ref.sha256) is True


def test_no_temp_files_left_after_save(tmp_path: Path):
    storage = LocalFileStorage(tmp_path)
    ref = storage.save(b"nguyen-tu-ghi", "doc.pdf")
    leaf_dir = tmp_path / ref.sha256[:2] / ref.sha256[2:4]
    assert [p for p in leaf_dir.iterdir() if p.name.startswith(".tmp")] == []
