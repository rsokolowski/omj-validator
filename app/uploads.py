"""Saving and sanitizing uploaded photos.

Shared by every upload endpoint - OMJ solutions, private task photos and
private task solutions - so the privacy guarantees (EXIF/GPS stripped, nothing
left on disk after a rejected request) hold everywhere, not just where they
were first written.
"""

import asyncio
import logging
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor
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

# Largest photo we agree to decode, in pixels. A PNG compresses a blank
# 12000x12000 page into half a megabyte, and decoding it took 16 s of CPU and
# 3.3 GB of RAM on the single production worker - a decompression bomb well
# under the upload size limit. 50 MP still admits the 48 MP mode of recent
# phones (8064x6048); anything bigger is refused from its header, before a
# single pixel is decoded (normalize_uploaded_image). Pillow's process-wide
# guard is left alone; its hard error (well above this cap) is caught too.
MAX_IMAGE_PIXELS = 50_000_000

# Decoding runs in these threads, never on the event loop: one slow photo must
# not freeze every other request (and the WebSockets) of the single worker. Two
# at a time also caps the memory a burst of large photos can take - a
# transparent photo at the pixel cap peaks at roughly 0.5 GB while normalized.
IMAGE_DECODE_WORKERS = 2
_image_executor = ThreadPoolExecutor(
    max_workers=IMAGE_DECODE_WORKERS, thread_name_prefix="image-normalize"
)


class ImageTooLargeError(Exception):
    """The photo has more pixels than MAX_IMAGE_PIXELS; it was not decoded."""


class UndecodablePhotoResponse(JSONResponse):
    """The 400 for a batch refused while its photos were being decoded.

    The cheap checks (byte size, header, decoder) run on the whole batch
    first, so this refusal means real decoding work was already spent on the
    request: a submission refused this way keeps using its daily slot (see
    settle_refused_submission). The cheap refusals before it are plain
    JSONResponses and give the slot back.
    """


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


def too_large_image_message(filename: OptionalType[str]) -> str:
    """Polish error for a photo over MAX_IMAGE_PIXELS."""
    name = filename or "zdjęcie"
    return (
        f"Plik {name} ma za dużą rozdzielczość (maksymalnie "
        f"{MAX_IMAGE_PIXELS // 1_000_000} megapikseli). Zmniejsz zdjęcie i prześlij ponownie."
    )


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

    # Pasted through its own alpha onto an RGB page: the same picture as
    # alpha_composite onto opaque white, without the extra full-size RGBA
    # buffers (a 50 MP page went from ~1 GB to ~0.5 GB at peak).
    rgba = img if img.mode == "RGBA" else img.convert("RGBA")
    page = Image.new("RGB", rgba.size, (255, 255, 255))
    page.paste(rgba, (0, 0), rgba)
    return page


def header_refusal(file_path: Path, filename: OptionalType[str], ext: str) -> OptionalType[str]:
    """Polish refusal for a photo unusable judging by its header alone, else None.

    Reads no pixel data - Image.open only parses the header - so it is the
    cheap pre-check save_uploaded_images runs on a whole batch before decoding
    any of it: too many pixels, or nothing that can read the file (not an
    image, or HEIC without its decoder).
    """
    try:
        with Image.open(file_path) as img:
            too_large = img.width * img.height > MAX_IMAGE_PIXELS
    except Image.DecompressionBombError:
        too_large = True
    except Exception as e:
        logger.warning(f"Image refused for {file_path.suffix}: unreadable header ({type(e).__name__})")
        return unprocessable_image_message(filename, ext)
    if too_large:
        logger.warning(f"Image refused for {file_path.suffix}: too many pixels")
        return too_large_image_message(filename)
    return None


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

    A photo over MAX_IMAGE_PIXELS raises ImageTooLargeError instead, so the
    student is told what is actually wrong with it. The size comes from the
    header; nothing is decoded first.

    Blocking and CPU/memory heavy - save_uploaded_images runs it in a thread.
    """
    tmp_path = file_path.with_name(file_path.name + ".tmp.jpg")
    target_path = file_path.with_suffix(".jpg")

    try:
        with Image.open(file_path) as img:
            # Before load/convert: the header alone says how big the decode is
            if img.width * img.height > MAX_IMAGE_PIXELS:
                raise ImageTooLargeError(f"{img.width}x{img.height}")

            # Camera rotation flag first, metadata removal second. In place: a
            # rotated copy would be one more full-size image in memory.
            ImageOps.exif_transpose(img, in_place=True)

            # Flatten BEFORE resizing: resampling an RGBA image blends the RGB
            # values hiding under transparent pixels into their neighbours, which
            # would leave a dark halo around the handwriting.
            flattened = flatten_transparency(img)

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
    except (ImageTooLargeError, Image.DecompressionBombError) as e:
        tmp_path.unlink(missing_ok=True)
        logger.warning(f"Image refused for {file_path.suffix}: too many pixels ({e})")
        raise ImageTooLargeError(str(e)) from None
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
    """400 response for an oversized or wrongly typed batch, else None.

    Emptiness is validate_submission_input's business.
    """
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


def normalize_solution_text(raw: OptionalType[str]) -> OptionalType[str]:
    """Canonical form of a typed solution, or None when there is nothing in it.

    Line endings become "\\n"; every other control character (Unicode category
    Cc - this includes the NUL byte PostgreSQL refuses in a text column) is
    dropped except tab; surrounding whitespace is stripped. The frontend applies
    the same rule (normalizeSolutionText in lib/utils/solutionText.ts), so the
    counter a student sees and the cap the server enforces agree.
    """
    if raw is None:
        return None
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(
        ch for ch in text if ch in ("\n", "\t") or unicodedata.category(ch) != "Cc"
    )
    text = text.strip()
    return text or None


def validate_submission_input(
    images: list[UploadFile], solution_text: OptionalType[str]
) -> tuple[OptionalType[str], OptionalType[JSONResponse]]:
    """Normalise the typed text and check the submission has something to grade.

    Returns (text, None) on success - text is None for a photos-only
    submission - or (None, 400 response). Runs before anything is written to
    disk, so a rejected request leaves nothing to clean up. Shared by the OMJ
    and the private task submit endpoints.
    """
    text = normalize_solution_text(solution_text)
    if not images and text is None:
        return None, JSONResponse(
            {"error": "Prześlij zdjęcia, rysunek albo wpisz rozwiązanie"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if text is not None and len(text) > settings.submission_text_max_chars:
        # "20 000", the way the counter in the browser formats it
        limit = f"{settings.submission_text_max_chars:,}".replace(",", " ")
        return None, JSONResponse(
            {"error": f"Rozwiązanie jest za długie (maksymalnie {limit} znaków)"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if images:
        batch_error = validate_image_batch(images)
        if batch_error is not None:
            return None, batch_error
    return text, None


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
    so tests can substitute it. It runs in _image_executor, off the event loop.
    """
    normalize = normalize or (lambda p: normalize_uploaded_image(p))
    max_size = settings.upload_max_size_mb * 1024 * 1024
    loop = asyncio.get_running_loop()

    # Every path this call may have put on disk (raw uploads and their
    # normalized copies); discard_uploads skips the ones already gone.
    on_disk: list[Path] = []

    # One guard around everything: every exit between "bytes hit the disk"
    # and "the DB row exists" must clean up after itself, otherwise a child's
    # photo stays on disk with nothing referencing it (see discard_uploads).
    try:
        # Pass 1 - cheap checks on EVERY photo before any is decoded: the byte
        # size while streaming, then the header (pixel count, a decoder that
        # can read it). A refusal here has cost no decoding, so the caller may
        # give the submission slot back. Once pass 2 starts it may not:
        # otherwise nine photos at the pixel cap followed by one oversized file
        # would be a free, repeatable way to burn seconds of CPU and gigabytes.
        written: list[tuple[UploadFile, str, Path]] = []
        for img in images:
            # Validate and normalize extension
            ext = Path(img.filename).suffix.lower() if img.filename else ".jpg"
            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                ext = ".jpg"  # Default to jpg for safety

            file_path = upload_dir / f"{uuid.uuid4().hex[:12]}{ext}"
            on_disk.append(file_path)

            # Read file in chunks with size limit check
            total_size = 0
            CHUNK_SIZE = 64 * 1024  # 64KB chunks
            upload_dir.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                while True:
                    chunk = await img.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > max_size:
                        f.close()
                        discard_uploads(on_disk)
                        return [], JSONResponse(
                            {"error": f"Plik {img.filename} jest za duży (max {settings.upload_max_size_mb}MB)"},
                            status_code=status.HTTP_400_BAD_REQUEST,
                        )
                    f.write(chunk)
            written.append((img, ext, file_path))

        for img, ext, file_path in written:
            refusal = await loop.run_in_executor(
                _image_executor, header_refusal, file_path, img.filename, ext
            )
            if refusal is not None:
                discard_uploads(on_disk)
                return [], JSONResponse({"error": refusal}, status_code=status.HTTP_400_BAD_REQUEST)

        # Pass 2 - strip EXIF/GPS, fix orientation, downscale. Returns the final
        # path - normalization always re-encodes to JPEG, so the name can change.
        saved_paths: list[Path] = []
        for img, ext, file_path in written:
            try:
                normalized_path = await loop.run_in_executor(_image_executor, normalize, file_path)
            except ImageTooLargeError:
                # Its header passed pass 1, so this is no honest mistake
                normalized_path = None
            if normalized_path is None:
                # Could not be decoded, so its metadata could not be removed
                # either. Storing it would ship the photo's GPS coordinates to
                # disk and to Google, so the upload is refused instead.
                discard_uploads(on_disk)
                return [], UndecodablePhotoResponse(
                    {"error": unprocessable_image_message(img.filename, ext)},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            on_disk.append(normalized_path)
            saved_paths.append(normalized_path)
    except BaseException:
        # BaseException: a cancelled request (shutdown, client gone) must clean
        # up too - every await on the decode threads is a cancellation point.
        discard_uploads(on_disk)
        raise

    return saved_paths, None
