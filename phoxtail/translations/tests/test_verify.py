"""`make translations-check`: the committed lists against a fresh gather, without running makemessages."""

import pytest

from phoxtail.translations import verify

HEADER = 'msgid ""\nmsgstr ""\n"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'


@pytest.fixture
def lists(tmp_path, monkeypatch):
    """A committed list and the gather's, in a package of their own."""
    package = tmp_path / "repo" / "phoxtail"
    committed = package / "translations" / "locale" / "el" / "LC_MESSAGES" / "django.po"
    committed.parent.mkdir(parents=True)
    monkeypatch.setattr(verify, "LOCALE", package / "translations" / "locale")
    monkeypatch.setattr(verify, "PACKAGE", package)

    def write(committed_text, gathered_text):
        committed.write_text(HEADER + committed_text, encoding="utf-8")

        def gather(arguments, copy):
            gathered = copy / "phoxtail" / "translations" / "locale" / "el" / "LC_MESSAGES" / "django.po"
            gathered.parent.mkdir(parents=True)
            gathered.write_text(HEADER + gathered_text, encoding="utf-8")

        monkeypatch.setattr(verify, "gather", gather)

    return write


def _run(capsys):
    with pytest.raises(SystemExit) as stop:
        verify.main()
    return stop.value.code, capsys.readouterr().out


def test_where_a_sentence_sits_is_not_compared(lists, capsys):
    lists('#: a.py:1\nmsgid "Save"\nmsgstr "Αποθήκευση"\n', '#: a.py:9\nmsgid "Save"\nmsgstr "Αποθήκευση"\n')

    assert _run(capsys) == (False, "translations up to date\n")


def test_a_new_and_a_gone_sentence_are_named(lists, capsys):
    lists(
        'msgid "Save"\nmsgstr "Αποθήκευση"\n',
        'msgctxt "button"\nmsgid "Send"\nmsgstr ""\n',
    )
    code, out = _run(capsys)

    assert code is True
    assert "el: new 'Send' (button)" in out
    assert "el: gone 'Save'" in out


def test_a_sentence_left_to_translate_fails(lists, capsys):
    lists('msgid "Save"\nmsgstr ""\n', 'msgid "Save"\nmsgstr ""\n')
    code, out = _run(capsys)

    assert code is True
    assert "el: to translate 'Save'" in out
