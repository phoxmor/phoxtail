"""Tests for cli.media."""

from phoxtail.cli.media import _parse_rsync_stats


class TestParseRsyncStats:
    SAMPLE_OUTPUT = """\
Number of files: 156 (reg: 142, dir: 14)
Number of created files: 0
Number of deleted files: 0
Number of regular files transferred: 12
Total file size: 45,678,912 bytes
Total transferred file size: 3,145,728 bytes
Literal data: 3,145,728 bytes
Matched data: 0 bytes
File list size: 4,096
File list generation time: 0.001 seconds
File list transfer time: 0.000 seconds
Total bytes sent: 248
Total bytes received: 3,150,072
sent 248 bytes  received 3,150,072 bytes  1,260,128.00 bytes/sec
total size is 45,678,912  speedup is 14.50
"""

    def test_parses_file_count(self):
        stats = _parse_rsync_stats(self.SAMPLE_OUTPUT)
        assert stats["files"] == 12

    def test_parses_size_as_mb(self):
        stats = _parse_rsync_stats(self.SAMPLE_OUTPUT)
        assert stats["size"] == "3.0 MB"

    def test_parses_gb_size(self):
        output = "Number of regular files transferred: 5\nTotal transferred file size: 2,147,483,648 bytes"
        stats = _parse_rsync_stats(output)
        assert stats["size"] == "2.0 GB"

    def test_parses_kb_size(self):
        output = "Number of regular files transferred: 1\nTotal transferred file size: 2,048 bytes"
        stats = _parse_rsync_stats(output)
        assert stats["size"] == "2.0 KB"

    def test_parses_bytes_size(self):
        output = "Number of regular files transferred: 1\nTotal transferred file size: 500 bytes"
        stats = _parse_rsync_stats(output)
        assert stats["size"] == "500 bytes"

    def test_zero_files_transferred(self):
        output = "Number of regular files transferred: 0\nTotal transferred file size: 0 bytes"
        stats = _parse_rsync_stats(output)
        assert stats["files"] == 0
        assert stats["size"] == "0 bytes"

    def test_empty_output_returns_empty_dict(self):
        stats = _parse_rsync_stats("")
        assert stats == {}

    def test_handles_large_comma_separated_numbers(self):
        output = "Number of regular files transferred: 1,234\nTotal transferred file size: 1,234,567,890 bytes"
        stats = _parse_rsync_stats(output)
        assert stats["files"] == 1234
        assert stats["size"] == "1.1 GB"
