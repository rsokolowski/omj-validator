"""Saving and sanitizing uploaded photos.

Shared by every upload endpoint - OMJ solutions, private task photos and
private task solutions - so the privacy guarantees (EXIF/GPS stripped, nothing
left on disk after a rejected request) hold everywhere, not just where they
were first written.
"""

import logging
import uuid
from pathlib import Path
from typing import Callable, Optional as OptionalType

from fastapi import UploadFile, status
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps

from .config import settings

logger = logging.getLogger(__name__)

def register_heif_decoder() -> bool:
    """Teach Pillow to read HEIC/HEIF, returning whether it worked.

    iPhones upload HEIC. We must be able to DECODE it, because that is the only
    way to strip its EXIF - and HEIC from a phone routinely carries GPS
    coordinates, i.e. the child's home address, which used to be written to disk
    and forwarded to Google untouched.

    pillow-heif is treated as optional: if it is missing or fails to register,
    the app still starts and HEIC uploads degrade to the explicit refusal in
    normalize_uploaded_image instead of taking the whole service down.
    """
    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        return True
    except Exception as e:
        logger.warning(
            f"HEIF decoder unavailable ({type(e).__name__}: {e}) - HEIC uploads "
            "will be refused, because their EXIF/GPS cannot be stripped. "
            "Install pillow-heif to accept them."
        )
        return False


HEIF_SUPPORTED = register_heif_decoder()
# Max image dimensions for AI API compatibility
MAX_IMAGE_DIMENSION = 2048


def discard_uploads(saved_paths: list[Path], current: OptionalType[Path] = None) -> None:
    """Remove every file written by a submission request that ends in an error.

    A rejected request must not leave a child's photo on disk with no DB row
    pointing at it - nothing else would ever look at it again, and with
    retention disabled (the local default) it would sit there forever.
    Only paths produced by this request are touched.
    """
    for path in list(saved_paths) + ([current] if current else []):
        try:
            path.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"Could not discard rejected upload: {type(e).__name__}: {e}")
    saved_paths.clear()


HEIF_EXTENSIONS = {".heic", ".heif"}


def unprocessable_image_message(filename: OptionalType[str], ext: str) -> str:
    """Polish error for a photo we could not sanitize, aimed at a 10-15 year old."""
    name = filename or "zdjęcie"
    if ext in HEIF_EXTENSIONS and not HEIF_SUPPORTED:
        # Server-side gap, not the child's fault - say what to do about it
        return (
            f"Nie umiemy teraz przetworzyć pliku {name} (format HEIC z iPhone'a). "
            "Zapisz zdjęcie jako JPG i prześlij ponownie."
        )
    return (
        f"Nie udało się przetworzyć pliku {name}. "
        "Prześlij zdjęcie w formacie JPG lub PNG."
    )


def flatten_transparency(img: Image.Image) -> Image.Image:
    """Return an RGB image, compositing any transparency onto WHITE.

    JPEG has no alpha channel, and Image.convert("RGB") drops it without
    compositing: a fully transparent pixel keeps whatever RGB value it happened
    to carry. For the standard "export with transparent background" from a
    tablet note-taking app that value is (0, 0, 0), so the entire page turns
    black - the student sends a correct solution and gets zero points with a
    comment about a blank sheet, having burnt one of their daily submissions.
    The same happens to a palette PNG carrying `transparency` in info.

    White, because a sheet of paper is white: the model then sees what the
    student saw on screen, dark handwriting on a light background.
    """
    # Covers RGBA and LA (alpha band present), PA, and palette images whose
    # transparency lives in info rather than in a band.
    has_alpha = "A" in img.getbands() or (
        img.mode in ("P", "PA") and "transparency" in img.info
    )
    if not has_alpha:
        return img.convert("RGB")

    rgba = img.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(background, rgba).convert("RGB")


def normalize_uploaded_image(file_path: Path) -> OptionalType[Path]:
    """Strip metadata, fix orientation and downscale an uploaded photo.

    Returns the path the normalized image ended up at - it is NOT always the
    input path, because everything is re-encoded as JPEG. Callers must use the
    returned path, otherwise the DB would reference a file that no longer
    exists. Returns None when the image could not be sanitized at all; the
    caller must then reject the upload rather than store it.

    Why every image and not just the big ones: these are phone photos of a
    child's handwriting, and the EXIF block routinely carries GPS coordinates -
    in practice the child's home address - which we would otherwise store on
    disk and forward to Google. Metadata used to be dropped only as a side
    effect of re-encoding during a resize, so a cropped photo, a screenshot or
    an older camera's output kept its EXIF. Privacy must not depend on the
    camera's resolution.

    Orientation is applied BEFORE the metadata is dropped (ImageOps.exif_transpose
    handles all 8 orientation values, not just the three the old code knew), so
    portrait photos do not end up sideways once the EXIF flag is gone.

    HEIC/HEIF goes through the same path as everything else thanks to
    pillow-heif (registered at import, see register_heif_decoder): decode,
    orient, drop metadata, re-encode as JPEG. If that decoder is unavailable,
    HEIC lands in the failure branch below.

    Transparency is composited onto white rather than discarded - see
    flatten_transparency for why that is not optional.

    A file Pillow cannot decode cannot have its metadata removed either, so it
    is refused instead of being stored as-is - storing an un-sanitizable photo
    would defeat the whole point of this function.
    """
    tmp_path = file_path.with_name(file_path.name + ".tmp.jpg")
    target_path = file_path.with_suffix(".jpg")

    try:
        with Image.open(file_path) as img:
            # Camera rotation flag first, metadata removal second
            oriented = ImageOps.exif_transpose(img) or img

            # Flatten BEFORE resizing: resampling an RGBA image blends the RGB
            # values hiding under transparent pixels into their neighbours, which
            # would leave a dark halo around the handwriting.
            flattened = flatten_transparency(oriented)

            if flattened.width > MAX_IMAGE_DIMENSION or flattened.height > MAX_IMAGE_DIMENSION:
                ratio = min(
                    MAX_IMAGE_DIMENSION / flattened.width,
                    MAX_IMAGE_DIMENSION / flattened.height,
                )
                new_size = (
                    max(1, int(flattened.width * ratio)),
                    max(1, int(flattened.height * ratio)),
                )
                flattened = flattened.resize(new_size, Image.Resampling.LANCZOS)

            # A fresh JPEG written from pixel data only: no EXIF, no GPS, no XMP.
            # Written to a temp file first so a failure mid-encode cannot destroy
            # the upload we already have.
            flattened.save(tmp_path, "JPEG", quality=85)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        logger.warning(
            f"Image normalization failed for {file_path.suffix}: "
            f"{type(e).__name__}: {e} - upload refused (metadata cannot be stripped)"
        )
        return None

    try:
        tmp_path.replace(target_path)
        if target_path != file_path:
            file_path.unlink(missing_ok=True)
    except OSError as e:
        tmp_path.unlink(missing_ok=True)
        logger.warning(f"Could not replace {file_path.name} with normalized image: {e}")
        return None

    return target_path


# Accepted upload MIME types. HEIC/HEIF included: pillow-heif decodes them so
# their EXIF (incl. GPS) can be stripped like any other format.
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_IMAGES = 10


def validate_image_batch(images: list[UploadFile]) -> OptionalType[JSONResponse]:
    """400 response for an empty, oversized or wrongly typed batch, else None."""
    if not images:
        return JSONResponse(
            {"error": "Nie przesłano żadnych zdjęć"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if len(images) > MAX_IMAGES:
        return JSONResponse(
            {"error": f"Maksymalnie {MAX_IMAGES} zdjęć na raz"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    for img in images:
        if img.content_type not in ALLOWED_IMAGE_TYPES:
            return JSONResponse(
                {"error": f"Niedozwolony typ pliku: {img.content_type}"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )
    return None


async def save_uploaded_images(
    images: list[UploadFile],
    upload_dir: Path,
    normalize: OptionalType[Callable[[Path], OptionalType[Path]]] = None,
) -> tuple[list[Path], OptionalType[JSONResponse]]:
    """Write, size-check and sanitize a batch of photos into upload_dir.

    Returns (saved_paths, None) on success or ([], error_response) when the
    batch was refused - in which case every file this call wrote is already
    gone. An unexpected exception also cleans up before propagating.

    ``normalize`` defaults to normalize_uploaded_image, looked up at call time
    so tests can substitute it.
    """
    normalize = normalize or (lambda p: normalize_uploaded_image(p))
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: list[Path] = []
    max_size = settings.upload_max_size_mb * 1024 * 1024

    # File currently being written - not yet in saved_paths, but just as much an
    # orphan as the rest if this request ends without creating a DB row.
    in_progress: OptionalType[Path] = None

    # One guard around the whole loop: every exit between "bytes hit the disk"
    # and "the DB row exists" must clean up after itself, otherwise a child's
    # photo stays on disk with nothing referencing it (see discard_uploads).
    try:
        for img in images:
            # Validate and normalize extension
            ext = Path(img.filename).suffix.lower() if img.filename else ".jpg"
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                ext = ".jpg"  # Default to jpg for safety

            filename = f"{uuid.uuid4().hex[:12]}{ext}"
            file_path = upload_dir / filename
            in_progress = file_path

            # Read file in chunks with size limit check
            total_size = 0
            CHUNK_SIZE = 64 * 1024  # 64KB chunks
            with open(file_path, "wb") as f:
                while True:
                    chunk = await img.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > max_size:
                        f.close()
                        discard_uploads(saved_paths, file_path)
                        return [], JSONResponse(
                            {"error": f"Plik {img.filename} jest za duży (max {settings.upload_max_size_mb}MB)"},
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )
                    f.write(chunk)

            # Strip EXIF/GPS, fix orientation, downscale. Returns the final path -
            # normalization always re-encodes to JPEG, so the name can change.
            normalized_path = normalize(file_path)
            if normalized_path is None:
                # Could not be decoded, so its metadata could not be removed
                # either. Storing it would ship the photo's GPS coordinates to
                # disk and to Google, so the upload is refused instead.
                discard_uploads(saved_paths, file_path)
                return [], JSONResponse(
                    {"error": unprocessable_image_message(img.filename, ext)},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

            saved_paths.append(normalized_path)
            in_progress = None
    except Exception:
        discard_uploads(saved_paths, in_progress)
        raise

    return saved_paths, None
