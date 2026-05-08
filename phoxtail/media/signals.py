import json
import logging
import os
import subprocess
import tempfile
import threading

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

_in_progress = threading.local()


def connect():
    from django.db.models.signals import post_save

    from phoxtail.media.models import PhoxtailMedia

    post_save.connect(_on_media_save, sender=PhoxtailMedia)


def _should_process(instance) -> bool:
    if instance.type == "video":
        return (
            not instance.thumbnail
            or not instance.duration
            or instance.width is None
            or instance.height is None
        )
    if instance.type == "audio":
        return not instance.duration
    return False


def _on_media_save(sender, instance, **kwargs):
    if not _should_process(instance):
        return

    pks = getattr(_in_progress, "pks", None)
    if pks is None:
        _in_progress.pks = set()
        pks = _in_progress.pks
    if instance.pk in pks:
        return

    pks.add(instance.pk)
    try:
        _process_media(instance)
    except Exception:
        logger.exception("Media post-processing failed for media pk=%s", instance.pk)
    finally:
        pks.discard(instance.pk)


def _process_media(instance):
    with default_storage.open(instance.file.name, "rb") as src:
        suffix = os.path.splitext(instance.file.name)[1] or ".mp4"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
            tmp_in.write(src.read())
            tmp_in_path = tmp_in.name

    try:
        update_fields: list[str] = []
        _fill_dimensions(instance, tmp_in_path, update_fields)
        if instance.type == "video":
            _fill_thumbnail(instance, tmp_in_path, update_fields)
        if update_fields:
            instance.save(update_fields=update_fields)
    finally:
        os.unlink(tmp_in_path)


def _fill_dimensions(instance, video_path: str, update_fields: list[str]) -> None:
    needs_duration = not instance.duration
    needs_width = instance.width is None
    needs_height = instance.height is None
    if not (needs_duration or needs_width or needs_height):
        return

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        logger.warning("ffprobe failed for media pk=%s", instance.pk)
        return

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    if needs_duration:
        raw = (streams[0].get("duration") if streams else None) or fmt.get("duration")
        if raw:
            instance.duration = float(raw)
            update_fields.append("duration")

    if needs_width and streams and streams[0].get("width"):
        instance.width = int(streams[0]["width"])
        update_fields.append("width")

    if needs_height and streams and streams[0].get("height"):
        instance.height = int(streams[0]["height"])
        update_fields.append("height")


def _fill_thumbnail(instance, video_path: str, update_fields: list[str]) -> None:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp_out:
        tmp_out_path = tmp_out.name

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
                "-vf",
                "thumbnail",
                "-frames:v",
                "1",
                "-y",
                tmp_out_path,
            ],
            capture_output=True,
            timeout=120,
            check=True,
        )
        with open(tmp_out_path, "rb") as f:
            stem = os.path.splitext(os.path.basename(instance.file.name))[0]
            instance.thumbnail.save(
                f"{stem}_thumb.jpg",
                ContentFile(f.read()),
                save=False,
            )
        update_fields.append("thumbnail")
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        logger.warning(
            "ffmpeg thumbnail extraction failed for media pk=%s", instance.pk
        )
    finally:
        os.unlink(tmp_out_path)
