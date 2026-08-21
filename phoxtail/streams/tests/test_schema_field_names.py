"""The schema block names are stored data, not just code.

Every name below is written into ``Block.schema`` and lives in the database of
every project that has ever defined a block. Renaming one raises no import
error and breaks no install — it breaks stored content, in projects that
upgraded without changing anything themselves.

Adding a name here is safe and the test expects it. Removing or renaming one is
a data migration, and this test is the thing that says so before the rename
reaches a release.
"""

from phoxtail.streams.models import Block

PERSISTED_SCHEMA_FIELD_NAMES = {
    "audio_chooser_field",
    "blockquote_field",
    "boolean_field",
    "char_field",
    "choice_field",
    "date_field",
    "datetime_field",
    "decimal_field",
    "document_chooser_field",
    "email_field",
    "embed_field",
    "float_field",
    "image_chooser_field",
    "image_field",
    "integer_field",
    "list_field",
    "list_struct",
    "multiple_choice_field",
    "page_chooser_field",
    "raw_html_field",
    "regex_field",
    "rich_text_field",
    "snippet_chooser_field",
    "stream",
    "struct",
    "text_field",
    "time_field",
    "url_field",
    "video_chooser_field",
}


def _declared_names():
    return set(Block.schema.field.stream_block.child_blocks)


def test_no_persisted_schema_field_name_is_removed_or_renamed():
    missing = PERSISTED_SCHEMA_FIELD_NAMES - _declared_names()
    assert not missing, (
        f"schema field name(s) removed or renamed: {sorted(missing)}. "
        "These strings are stored in Block.schema in existing databases; "
        "changing one needs a data migration, not just an edit here."
    )


def test_new_schema_field_names_are_recorded():
    added = _declared_names() - PERSISTED_SCHEMA_FIELD_NAMES
    assert not added, (
        f"new schema field name(s): {sorted(added)}. Adding one is safe — "
        "record it in PERSISTED_SCHEMA_FIELD_NAMES so a later rename is caught."
    )
