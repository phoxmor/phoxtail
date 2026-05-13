"""Tests for phoxtail.media post-save video processing."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

from phoxtail.media.signals import (
    _fill_dimensions,
    _fill_thumbnail,
    _on_media_save,
    _process_media,
)


def _make_media(type="video", thumbnail="", duration=0.0, width=None, height=None):
    m = MagicMock()
    m.pk = 1
    m.type = type
    m.thumbnail = MagicMock()
    m.thumbnail.__bool__ = lambda self: bool(thumbnail)
    m.duration = duration
    m.width = width
    m.height = height
    m.file.name = "media/test.mp4"
    return m


FFPROBE_OUTPUT = json.dumps(
    {
        "streams": [{"width": 1920, "height": 1080, "duration": "42.5"}],
        "format": {"duration": "42.5"},
    }
)


class TestSignalGating:
    def test_skips_audio_with_duration(self):
        m = _make_media(type="audio", duration=30.0)
        with patch("phoxtail.media.signals._process_media") as proc:
            _on_media_save(sender=None, instance=m)
        proc.assert_not_called()

    def test_fires_for_audio_without_duration(self):
        m = _make_media(type="audio", duration=0.0)
        with patch("phoxtail.media.signals._process_media") as proc:
            _on_media_save(sender=None, instance=m)
        proc.assert_called_once_with(m)

    def test_skips_when_video_fully_populated(self):
        m = _make_media(type="video", thumbnail="t.jpg", duration=10.0, width=1920, height=1080)
        with patch("phoxtail.media.signals._process_media") as proc:
            _on_media_save(sender=None, instance=m)
        proc.assert_not_called()

    def test_fires_for_video_without_thumbnail(self):
        m = _make_media(type="video", thumbnail="", duration=10.0, width=1920, height=1080)
        with patch("phoxtail.media.signals._process_media") as proc:
            _on_media_save(sender=None, instance=m)
        proc.assert_called_once_with(m)

    def test_fires_for_video_without_duration(self):
        m = _make_media(type="video", thumbnail="t.jpg", duration=0.0, width=1920, height=1080)
        with patch("phoxtail.media.signals._process_media") as proc:
            _on_media_save(sender=None, instance=m)
        proc.assert_called_once_with(m)

    def test_exception_does_not_propagate(self):
        m = _make_media(type="video", thumbnail="")
        with patch("phoxtail.media.signals._process_media", side_effect=RuntimeError("boom")):
            _on_media_save(sender=None, instance=m)  # must not raise


class TestProcessMedia:
    def test_audio_does_not_call_fill_thumbnail(self):
        m = _make_media(type="audio", duration=0.0)
        with (
            patch("phoxtail.media.signals._fill_dimensions"),
            patch("phoxtail.media.signals._fill_thumbnail") as mock_thumb,
            patch("phoxtail.media.signals.default_storage") as mock_storage,
            patch("tempfile.NamedTemporaryFile") as mock_tmp,
            patch("os.unlink"),
        ):
            mock_storage.open.return_value.__enter__ = lambda s: MagicMock(read=lambda: b"")
            mock_storage.open.return_value.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value.__enter__ = lambda s: s
            mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value.name = "/tmp/audio.mp3"
            _process_media(m)
        mock_thumb.assert_not_called()

    def test_video_calls_fill_thumbnail(self):
        m = _make_media(type="video", thumbnail="")
        with (
            patch("phoxtail.media.signals._fill_dimensions"),
            patch("phoxtail.media.signals._fill_thumbnail") as mock_thumb,
            patch("phoxtail.media.signals.default_storage") as mock_storage,
            patch("tempfile.NamedTemporaryFile") as mock_tmp,
            patch("os.unlink"),
        ):
            mock_storage.open.return_value.__enter__ = lambda s: MagicMock(read=lambda: b"")
            mock_storage.open.return_value.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value.__enter__ = lambda s: s
            mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value.name = "/tmp/video.mp4"
            _process_media(m)
        mock_thumb.assert_called_once()


class TestFillDimensions:
    def _run(self, instance, stdout):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=stdout)
            update_fields: list[str] = []
            _fill_dimensions(instance, "/tmp/fake.mp4", update_fields)
            return update_fields, mock_run

    def test_fills_duration_width_height(self):
        m = _make_media(duration=0.0, width=None, height=None)
        fields, _ = self._run(m, FFPROBE_OUTPUT)
        assert "duration" in fields
        assert "width" in fields
        assert "height" in fields
        assert m.duration == 42.5
        assert m.width == 1920
        assert m.height == 1080

    def test_skips_when_already_set(self):
        m = _make_media(duration=10.0, width=1280, height=720)
        fields, mock_run = self._run(m, FFPROBE_OUTPUT)
        mock_run.assert_not_called()
        assert fields == []

    def test_ffprobe_failure_is_silent(self):

        m = _make_media(duration=0.0, width=None, height=None)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            update_fields: list[str] = []
            _fill_dimensions(m, "/tmp/fake.mp4", update_fields)
        assert update_fields == []

    def test_uses_format_duration_when_stream_missing(self):
        output = json.dumps({"streams": [], "format": {"duration": "99.9"}})
        m = _make_media(duration=0.0, width=None, height=None)
        fields, _ = self._run(m, output)
        assert "duration" in fields
        assert m.duration == 99.9
        assert "width" not in fields


class TestFillThumbnail:
    def _run_ok(self, instance, jpg_data=b"FAKEJPEG"):
        with (
            patch("subprocess.run") as mock_run,
            patch("builtins.open", return_value=BytesIO(jpg_data)) as mock_open,
            patch("os.unlink"),
            patch("tempfile.NamedTemporaryFile") as mock_tmp,
        ):
            mock_tmp.return_value.__enter__ = lambda s: s
            mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value.name = "/tmp/thumb.jpg"
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            mock_open.return_value.read = lambda: jpg_data
            update_fields: list[str] = []
            _fill_thumbnail(instance, "/tmp/fake.mp4", update_fields)
            return update_fields, mock_run

    def test_saves_thumbnail_on_success(self):
        m = _make_media()
        update_fields: list[str] = []
        jpg = b"\xff\xd8\xff" + b"\x00" * 100

        with (
            patch("subprocess.run"),
            patch("os.unlink"),
            patch("tempfile.NamedTemporaryFile") as mock_tmp,
            patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=lambda s: s,
                        __exit__=MagicMock(return_value=False),
                        read=lambda: jpg,
                    )
                ),
            ),
        ):
            mock_tmp.return_value.__enter__ = lambda s: s
            mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value.name = "/tmp/out.jpg"
            _fill_thumbnail(m, "/tmp/fake.mp4", update_fields)

        assert "thumbnail" in update_fields
        m.thumbnail.save.assert_called_once()
        save_name = m.thumbnail.save.call_args[0][0]
        assert save_name.endswith("_thumb.jpg")

    def test_ffmpeg_failure_does_not_add_thumbnail_field(self):
        import subprocess

        m = _make_media()
        with (
            patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg")),
            patch("os.unlink"),
            patch("tempfile.NamedTemporaryFile") as mock_tmp,
        ):
            mock_tmp.return_value.__enter__ = lambda s: s
            mock_tmp.return_value.__exit__ = MagicMock(return_value=False)
            mock_tmp.return_value.name = "/tmp/out.jpg"
            update_fields: list[str] = []
            _fill_thumbnail(m, "/tmp/fake.mp4", update_fields)

        assert "thumbnail" not in update_fields
        m.thumbnail.save.assert_not_called()
