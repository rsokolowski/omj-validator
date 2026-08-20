"""Uploaded photos must never keep their EXIF - it usually carries GPS.

These are phone photos of a child's handwriting. Before this, metadata was only
dropped as a side effect of downscaling, so any image below the resize threshold
reached the disk (and Google) with the child's home coordinates attached.

The normalizer also renames files (everything becomes JPEG), so the "the DB must
not point at a file that no longer exists" cases are covered here too.
"""

import io

import piexif
import pytest
from PIL import Image, ImageDraw

import app.main as main
from app.main import (
    HEIF_SUPPORTED,
    MAX_IMAGE_DIMENSION,
    _flatten_transparency,
    _normalize_uploaded_image,
    _register_heif_decoder,
    _unprocessable_image_message,
)

# Somewhere in Warsaw - stands in for "the child's home address"
GPS_LATITUDE = ((52, 1), (13, 1), (0, 1))
GPS_LONGITUDE = ((21, 1), (0, 1), (0, 1))


def exif_bytes(orientation: int = 1, with_gps: bool = True) -> bytes:
    """Build an EXIF block with an orientation flag and (optionally) GPS."""
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Orientation: orientation,
            piexif.ImageIFD.Make: b"TestPhone",
        },
        "Exif": {},
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    if with_gps:
        exif_dict["GPS"] = {
            piexif.GPSIFD.GPSLatitudeRef: b"N",
            piexif.GPSIFD.GPSLatitude: GPS_LATITUDE,
            piexif.GPSIFD.GPSLongitudeRef: b"E",
            piexif.GPSIFD.GPSLongitude: GPS_LONGITUDE,
        }
    return piexif.dump(exif_dict)


def write_jpeg(path, size=(800, 600), orientation: int = 1, with_gps: bool = True):
    """Write a JPEG that carries EXIF, like a phone camera would."""
    img = Image.new("RGB", size, color=(120, 130, 140))
    img.save(path, "JPEG", exif=exif_bytes(orientation, with_gps))
    return path


def read_exif(path) -> dict:
    with Image.open(path) as img:
        return img.getexif() or {}


class TestExifRemoval:
    def test_small_image_loses_gps(self, tmp_path):
        """The regression: small photos used to skip normalization entirely."""
        source = write_jpeg(tmp_path / "photo.jpg", size=(800, 600))
        assert piexif.load(str(source))["GPS"], "fixture must start with GPS"

        result = _normalize_uploaded_image(source)

        assert not piexif.load(str(result))["GPS"]
        assert not read_exif(result)

    def test_large_image_loses_gps(self, tmp_path):
        source = write_jpeg(tmp_path / "photo.jpg", size=(MAX_IMAGE_DIMENSION + 500, 1200))

        result = _normalize_uploaded_image(source)

        assert not piexif.load(str(result))["GPS"]

    def test_no_camera_metadata_survives(self, tmp_path):
        source = write_jpeg(tmp_path / "photo.jpg")

        result = _normalize_uploaded_image(source)

        raw = result.read_bytes()
        assert b"TestPhone" not in raw

    def test_image_without_exif_still_works(self, tmp_path):
        path = tmp_path / "plain.jpg"
        Image.new("RGB", (500, 400), color="white").save(path, "JPEG")

        result = _normalize_uploaded_image(path)

        with Image.open(result) as img:
            assert img.size == (500, 400)


class TestOrientation:
    @pytest.mark.parametrize(
        "orientation,expected_size",
        [
            (1, (800, 600)),  # normal
            (3, (800, 600)),  # 180 deg - dimensions unchanged
            (6, (600, 800)),  # rotated 90 deg - dimensions swap
            (8, (600, 800)),  # rotated 270 deg - dimensions swap
            (5, (600, 800)),  # transposed - the old code ignored this one
            (7, (600, 800)),  # transverse - and this one
        ],
    )
    def test_rotation_is_baked_in_before_metadata_is_dropped(
        self, tmp_path, orientation, expected_size
    ):
        """Without this, dropping EXIF would leave portrait photos sideways."""
        source = write_jpeg(tmp_path / "photo.jpg", size=(800, 600), orientation=orientation)

        result = _normalize_uploaded_image(source)

        with Image.open(result) as img:
            assert img.size == expected_size
        assert not read_exif(result)


class TestResizing:
    def test_downscales_oversized_images(self, tmp_path):
        source = write_jpeg(tmp_path / "big.jpg", size=(MAX_IMAGE_DIMENSION * 2, 1000))

        result = _normalize_uploaded_image(source)

        with Image.open(result) as img:
            assert max(img.size) <= MAX_IMAGE_DIMENSION

    def test_does_not_upscale_small_images(self, tmp_path):
        source = write_jpeg(tmp_path / "small.jpg", size=(320, 240))

        result = _normalize_uploaded_image(source)

        with Image.open(result) as img:
            assert img.size == (320, 240)


class TestPathConsistency:
    """The returned path is what gets written to the DB - it must exist."""

    def test_jpeg_keeps_its_path(self, tmp_path):
        source = write_jpeg(tmp_path / "photo.jpg")

        result = _normalize_uploaded_image(source)

        assert result == source
        assert result.is_file()

    @pytest.mark.parametrize("suffix", [".png", ".webp", ".jpeg"])
    def test_other_formats_are_re_encoded_and_the_old_file_is_gone(self, tmp_path, suffix):
        source = tmp_path / f"photo{suffix}"
        Image.new("RGB", (400, 300), color="red").save(source)

        result = _normalize_uploaded_image(source)

        assert result == tmp_path / "photo.jpg"
        assert result.is_file()
        if suffix != ".jpg":
            assert not source.exists() or source == result
        # exactly one file left behind, no stray temp file
        assert sorted(p.name for p in tmp_path.iterdir()) == ["photo.jpg"]

    def test_small_png_is_also_re_encoded(self, tmp_path):
        """Small images used to be returned untouched, keeping the .png name."""
        source = tmp_path / "tiny.png"
        Image.new("RGB", (50, 50), color="blue").save(source)

        result = _normalize_uploaded_image(source)

        assert result.suffix == ".jpg"
        assert result.is_file()


class TestFailureHandling:
    def test_unsanitizable_file_is_refused(self, tmp_path):
        """A file Pillow cannot decode cannot have its metadata stripped either,
        so it must not be stored - that is what the None return signals."""
        source = tmp_path / "broken.jpg"
        source.write_bytes(b"this is not an image")

        assert _normalize_uploaded_image(source) is None
        # No half-written temp file left behind
        assert sorted(p.name for p in tmp_path.iterdir()) == ["broken.jpg"]

    def test_corrupt_heic_is_refused(self, tmp_path):
        """Even with a decoder registered, an undecodable file must not be kept."""
        source = tmp_path / "photo.heic"
        source.write_bytes(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)

        assert _normalize_uploaded_image(source) is None

    def test_no_temp_file_is_left_behind_on_success(self, tmp_path):
        write_jpeg(tmp_path / "photo.jpg")

        _normalize_uploaded_image(tmp_path / "photo.jpg")

        assert not any(p.name.endswith(".tmp.jpg") for p in tmp_path.iterdir())


class TestRejectedUploadLeavesNoFiles:
    """A rejected submission must not leave a child's photo on disk with no DB
    row pointing at it - with retention disabled (the local default) nothing
    would ever clean it up."""

    def test_discard_removes_every_file_from_the_request(self, tmp_path):
        from app.main import _discard_uploads

        first = tmp_path / "a.jpg"
        second = tmp_path / "b.jpg"
        current = tmp_path / "c.jpg"
        for path in (first, second, current):
            path.write_bytes(b"x")
        saved = [first, second]

        _discard_uploads(saved, current)

        assert list(tmp_path.iterdir()) == []
        assert saved == []

    def test_discard_tolerates_already_missing_files(self, tmp_path):
        from app.main import _discard_uploads

        missing = tmp_path / "gone.jpg"

        _discard_uploads([missing], None)  # must not raise

    def test_discard_only_touches_the_paths_it_is_given(self, tmp_path):
        from app.main import _discard_uploads

        keep = tmp_path / "someone-elses.jpg"
        keep.write_bytes(b"keep")
        mine = tmp_path / "mine.jpg"
        mine.write_bytes(b"x")

        _discard_uploads([mine])

        assert keep.exists()
        assert not mine.exists()


class TestHeifSupport:
    """iPhones upload HEIC. We must DECODE it to strip its EXIF - HEIC from a
    phone routinely carries GPS, i.e. the child's home address."""

    def test_decoder_is_registered_at_import(self):
        assert HEIF_SUPPORTED is True, "pillow-heif missing - HEIC uploads would be refused"

    def test_pillow_knows_the_heic_extension(self):
        assert Image.registered_extensions().get(".heic") == "HEIF"

    def test_registration_is_idempotent(self):
        assert _register_heif_decoder() is True

    def test_registration_degrades_instead_of_crashing(self, monkeypatch):
        """A missing/broken pillow-heif must not take the app down at startup."""
        import builtins

        real_import = builtins.__import__

        def blow_up(name, *args, **kwargs):
            if name == "pillow_heif":
                raise ImportError("no pillow_heif")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blow_up)

        assert _register_heif_decoder() is False

    def test_real_heic_is_normalized_and_loses_its_metadata(self, tmp_path):
        """End-to-end: a genuine HEIC goes in, a clean JPEG comes out."""
        pillow_heif = pytest.importorskip("pillow_heif")

        source = tmp_path / "iphone.heic"
        rgb = Image.new("RGB", (900, 600), color=(200, 100, 50))
        heif = pillow_heif.from_pillow(rgb)
        heif.save(str(source), quality=80)
        assert source.is_file()

        result = _normalize_uploaded_image(source)

        assert result is not None, "HEIC was refused despite pillow-heif being installed"
        assert result == tmp_path / "iphone.jpg"
        assert not source.exists()
        with Image.open(result) as img:
            assert img.format == "JPEG"
            assert img.size == (900, 600)
        assert not (Image.open(result).getexif() or {})

    def test_oversized_heic_is_also_downscaled(self, tmp_path):
        pillow_heif = pytest.importorskip("pillow_heif")

        source = tmp_path / "big.heic"
        rgb = Image.new("RGB", (MAX_IMAGE_DIMENSION + 400, 800), color="green")
        pillow_heif.from_pillow(rgb).save(str(source), quality=70)

        result = _normalize_uploaded_image(source)

        assert result is not None
        with Image.open(result) as img:
            assert max(img.size) <= MAX_IMAGE_DIMENSION


class TestUnprocessableMessage:
    """The 400 body a child actually reads."""

    def test_heic_without_decoder_gets_actionable_advice(self, monkeypatch):
        monkeypatch.setattr(main, "HEIF_SUPPORTED", False)

        message = _unprocessable_image_message("zdjecie.heic", ".heic")

        assert "HEIC" in message
        assert "JPG" in message
        assert "zdjecie.heic" in message

    def test_generic_message_for_other_formats(self):
        message = _unprocessable_image_message("skan.png", ".png")

        assert "JPG lub PNG" in message
        assert "skan.png" in message

    def test_heic_with_decoder_uses_the_generic_message(self, monkeypatch):
        """With a decoder available a HEIC failure is a corrupt file, not format."""
        monkeypatch.setattr(main, "HEIF_SUPPORTED", True)

        message = _unprocessable_image_message("zdjecie.heic", ".heic")

        assert "JPG lub PNG" in message

    def test_missing_filename_does_not_crash(self):
        assert "zdjęcie" in _unprocessable_image_message(None, ".jpg")


def stroke_on_transparent(mode: str, size=(300, 200)):
    """A page exported "with transparent background" from a tablet notes app:
    fully transparent everywhere, dark handwriting on top."""
    if mode == "RGBA":
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        ink = (0, 0, 0, 255)
    elif mode == "LA":
        img = Image.new("LA", size, (0, 0))
        ink = (0, 255)
    else:
        raise ValueError(mode)
    ImageDraw.Draw(img).line((20, size[1] // 2, size[0] - 20, size[1] // 2), fill=ink, width=6)
    return img


def palette_with_transparency(size=(300, 200)):
    """Palette PNG whose transparency lives in info, not in a band."""
    img = Image.new("P", size, 0)
    # index 0 = black (and transparent), index 1 = black ink
    img.putpalette([0, 0, 0] + [0, 0, 0] + [255, 255, 255] * 254)
    ImageDraw.Draw(img).line((20, size[1] // 2, size[0] - 20, size[1] // 2), fill=1, width=6)
    img.info["transparency"] = 0
    return img


def describe(path):
    """(number of distinct colours, background pixel, ink pixel)."""
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        return (
            len(rgb.getcolors(maxcolors=1_000_000)),
            rgb.getpixel((5, 5)),
            rgb.getpixel((rgb.width // 2, rgb.height // 2)),
        )


class TestTransparencyIsCompositedOnWhite:
    """Regression: normalizing every upload meant every transparent PNG went
    through convert("RGB"), which drops alpha WITHOUT compositing. A page
    exported with a transparent background became a uniformly black rectangle -
    the student got 0 points and a comment about a blank sheet, and lost one of
    their daily submissions with no way to tell what went wrong."""

    def test_rgba_page_keeps_dark_ink_on_light_background(self, tmp_path):
        source = tmp_path / "notes.png"
        stroke_on_transparent("RGBA").save(source)

        result = _normalize_uploaded_image(source)

        colors, background, ink = describe(result)
        assert colors > 1, "image collapsed to a single colour"
        assert background == (255, 255, 255)
        assert sum(ink) < sum(background), "handwriting is not darker than the page"

    def test_la_page_keeps_dark_ink_on_light_background(self, tmp_path):
        source = tmp_path / "notes.png"
        stroke_on_transparent("LA").save(source)

        result = _normalize_uploaded_image(source)

        colors, background, ink = describe(result)
        assert colors > 1
        assert background == (255, 255, 255)
        assert sum(ink) < sum(background)

    def test_palette_png_with_transparency_is_composited(self, tmp_path):
        source = tmp_path / "notes.png"
        palette_with_transparency().save(source, transparency=0)

        result = _normalize_uploaded_image(source)

        colors, background, ink = describe(result)
        assert colors > 1
        assert background == (255, 255, 255)
        assert sum(ink) < sum(background)

    def test_semi_transparent_ink_stays_visible(self, tmp_path):
        """Anti-aliased strokes are partly transparent; they must not vanish."""
        source = tmp_path / "notes.png"
        img = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
        ImageDraw.Draw(img).line((10, 50, 190, 50), fill=(0, 0, 0, 128), width=8)
        img.save(source)

        result = _normalize_uploaded_image(source)

        colors, background, ink = describe(result)
        assert background == (255, 255, 255)
        assert sum(ink) < sum(background), "semi-transparent ink disappeared into the page"

    def test_transparent_page_survives_downscaling(self, tmp_path):
        """Flattening happens before the resize, so no dark halo is resampled in."""
        source = tmp_path / "big.png"
        stroke_on_transparent("RGBA", size=(MAX_IMAGE_DIMENSION + 600, 900)).save(source)

        result = _normalize_uploaded_image(source)

        with Image.open(result) as img:
            assert max(img.size) <= MAX_IMAGE_DIMENSION
        colors, background, _ = describe(result)
        assert colors > 1
        assert background == (255, 255, 255)

    def test_opaque_images_are_untouched_by_the_compositing(self, tmp_path):
        """Guard against the fix washing out ordinary photos."""
        source = tmp_path / "photo.jpg"
        Image.new("RGB", (200, 150), (12, 34, 56)).save(source, "JPEG", quality=95)

        result = _normalize_uploaded_image(source)

        with Image.open(result) as img:
            r, g, b = img.convert("RGB").getpixel((100, 75))
        assert abs(r - 12) < 6 and abs(g - 34) < 6 and abs(b - 56) < 6

    def test_white_background_not_black(self, tmp_path):
        """The specific choice: paper is white, and black would hide the ink."""
        source = tmp_path / "notes.png"
        stroke_on_transparent("RGBA").save(source)

        result = _normalize_uploaded_image(source)

        _, background, _ = describe(result)
        assert background != (0, 0, 0)
        assert background == (255, 255, 255)


class TestFlattenTransparencyUnit:
    @pytest.mark.parametrize("mode", ["RGBA", "LA"])
    def test_alpha_modes_are_composited(self, mode):
        flattened = _flatten_transparency(stroke_on_transparent(mode))

        assert flattened.mode == "RGB"
        assert flattened.getpixel((5, 5)) == (255, 255, 255)

    def test_palette_transparency_is_detected(self):
        flattened = _flatten_transparency(palette_with_transparency())

        assert flattened.mode == "RGB"
        assert flattened.getpixel((5, 5)) == (255, 255, 255)

    def test_opaque_palette_is_just_converted(self):
        img = Image.new("P", (10, 10), 0)
        img.putpalette([7, 8, 9] * 256)

        flattened = _flatten_transparency(img)

        assert flattened.mode == "RGB"
        assert flattened.getpixel((5, 5)) == (7, 8, 9)

    def test_plain_rgb_is_unchanged(self):
        img = Image.new("RGB", (10, 10), (1, 2, 3))

        flattened = _flatten_transparency(img)

        assert flattened.mode == "RGB"
        assert flattened.getpixel((5, 5)) == (1, 2, 3)
