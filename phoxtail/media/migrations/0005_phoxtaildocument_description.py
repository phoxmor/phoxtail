from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_media", "0004_rename_phoxtailrendition_phoxtailimagerendition"),
    ]

    operations = [
        migrations.AddField(
            model_name="phoxtaildocument",
            name="description",
            field=models.TextField(blank=True, verbose_name="Description"),
        ),
    ]
