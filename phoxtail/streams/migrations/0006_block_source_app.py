from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_streams", "0005_blockcategory_block_categories"),
    ]

    operations = [
        migrations.AddField(
            model_name="block",
            name="source_app",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Django app label that owns this block (e.g. 'phoxtail_blog'). "
                    "Set automatically by populate_streams. Blank means no app dependency — "
                    "the block is available in any project."
                ),
                max_length=100,
            ),
        ),
    ]
