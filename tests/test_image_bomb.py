"""A photo is refused from its header when it has too many pixels.

Audit finding: a 546 KB transparent 12000x12000 PNG took ~16 s of CPU and
3.3 GB of RAM to "normalize" on the single production worker, synchronously on
the event loop. The pixel count is now checked before anything is decoded, and
decoding runs in a worker thread.
"""

import asyncio
import io
import struct
import threading
import time
import zlib

import pytest
from PIL import Image
from starlette.datastructures import Headers, UploadFile

import app.uploads as uploads
from app.config import settings


def png_header_only(width: int, height: int) -> bytes:
    """A PNG that claims width x height but carries a tiny (garbage) IDAT.

    Enough for Image.open to read the size - which is all the guard may look
    at - without the test itself allocating gigabytes.
    """

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00" * 1024))
        + chunk(b"IEND", b"")
    )


def png_bytes(size) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGBA", size, (0, 0, 0, 0)).save(buffer, "PNG")
    return buffer.getvalue()


def upload(name: str, data: bytes, content_type: str = "image/png") -> UploadFile:
    return UploadFile(
        io.BytesIO(data),
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


@pytest.fixture
def uploads_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    return tmp_path


class TestPixelCap:
    def test_bomb_is_refused_without_decoding(self, tmp_path):
        path = tmp_path / "bomb.png"
        path.write_bytes(png_header_only(12000, 12000))

        started = time.monotonic()
        with pytest.raises(uploads.ImageTooLargeError):
            uploads.normalize_uploaded_image(path)

        assert time.monotonic() - started < 2
        assert not (tmp_path / "bomb.png.tmp.jpg").exists()

    def test_just_over_the_cap_is_refused(self, tmp_path):
        """Between the cap and Pillow's 2x hard error it only warns - not enough."""
        side = int(uploads.MAX_IMAGE_PIXELS ** 0.5) + 10
        path = tmp_path / "big.png"
        path.write_bytes(png_header_only(side, side))

        with pytest.raises(uploads.ImageTooLargeError):
            uploads.normalize_uploaded_image(path)

    def test_cap_admits_48_megapixel_phone_photos(self):
        assert 8064 * 6048 <= uploads.MAX_IMAGE_PIXELS

    def test_pillow_guard_matches_the_cap(self):
        assert Image.MAX_IMAGE_PIXELS == uploads.MAX_IMAGE_PIXELS

    def test_cap_applies_to_heic(self, tmp_path, monkeypatch):
        pillow_heif = pytest.importorskip("pillow_heif")
        if not uploads.HEIF_SUPPORTED:
            pytest.skip("HEIF decoder not registered")
        monkeypatch.setattr(uploads, "MAX_IMAGE_PIXELS", 100 * 100)
        path = tmp_path / "IMG_0001.heic"
        pillow_heif.from_pillow(Image.new("RGB", (200, 200), (30, 60, 90))).save(
            str(path), quality=70
        )

        with pytest.raises(uploads.ImageTooLargeError):
            uploads.normalize_uploaded_image(path)

    def test_under_the_cap_still_normalizes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(uploads, "MAX_IMAGE_PIXELS", 100 * 100)
        path = tmp_path / "ok.png"
        path.write_bytes(png_bytes((100, 100)))

        result = uploads.normalize_uploaded_image(path)

        assert result is not None and result.suffix == ".jpg"


class TestSaveUploadedImages:
    def test_bomb_in_a_batch_is_400_and_leaves_nothing(self, uploads_root):
        target = settings.uploads_dir / "u" / "x"
        images = [
            upload("good.png", png_bytes((40, 40))),
            upload("bomb.png", png_header_only(12000, 12000)),
        ]

        saved, error = asyncio.run(uploads.save_uploaded_images(images, target))

        assert saved == []
        assert error is not None and error.status_code == 400
        assert b"rozdzielczo" in error.body
        assert not target.exists() or not any(p.is_file() for p in target.rglob("*"))

    def test_normalization_runs_off_the_event_loop(self, uploads_root):
        loop_threads = []
        normalize_threads = []

        def normalize(path):
            normalize_threads.append(threading.get_ident())
            return uploads.normalize_uploaded_image(path)

        async def run():
            loop_threads.append(threading.get_ident())
            return await uploads.save_uploaded_images(
                [upload("a.png", png_bytes((20, 20)))],
                settings.uploads_dir / "u",
                normalize=normalize,
            )

        saved, error = asyncio.run(run())

        assert error is None and len(saved) == 1
        assert normalize_threads and normalize_threads[0] != loop_threads[0]
