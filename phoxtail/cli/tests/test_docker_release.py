"""A release prints the commit of each package it upgrades."""

from phoxtail.cli.docker import _commit_moves, _locked_commits

LOCK = """\
version = 1

[[package]]
name = "phoxtail"
version = "0.2.0"
source = { git = "ssh://git@github.com/phoxmor/phoxtail.git?branch=main#a3716d50b4bb" }

[[package]]
name = "phoxtail-extras"
version = "0.1.1"
source = { git = "ssh://git@github.com/phoxmor/phoxtail-extras.git#d8612a521923" }

[[package]]
name = "django"
version = "5.2.15"
source = { registry = "https://pypi.org/simple" }
"""


class TestLockedCommits:
    def test_reads_the_commit_of_each_git_package(self, project_dir):
        (project_dir / "uv.lock").write_text(LOCK)
        assert _locked_commits(["phoxtail", "phoxtail-extras"]) == {
            "phoxtail": "a3716d50b4bb",
            "phoxtail-extras": "d8612a521923",
        }

    def test_ignores_packages_not_asked_for_or_not_from_git(self, project_dir):
        (project_dir / "uv.lock").write_text(LOCK)
        assert _locked_commits(["phoxtail", "django"]) == {"phoxtail": "a3716d50b4bb"}

    def test_no_lock_reads_as_nothing(self, project_dir):
        assert _locked_commits(["phoxtail"]) == {}


class TestCommitMoves:
    def test_a_moved_package_shows_both_commits(self):
        assert _commit_moves({"phoxtail": "a3716d50b4bb"}, {"phoxtail": "f3676ae00000"}) == [
            "phoxtail a3716d5 → f3676ae"
        ]

    def test_an_unmoved_package_says_so(self):
        assert _commit_moves({"phoxtail": "a3716d50b4bb"}, {"phoxtail": "a3716d50b4bb"}) == [
            "phoxtail a3716d5 (unchanged)"
        ]

    def test_a_newly_locked_package_shows_its_commit(self):
        assert _commit_moves({}, {"phoxtail": "a3716d50b4bb"}) == ["phoxtail a3716d5"]
