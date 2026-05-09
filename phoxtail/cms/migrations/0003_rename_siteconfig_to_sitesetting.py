from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('phoxtail_cms', '0002_alter_siteconfig_favicon_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='SiteConfig',
            new_name='SiteSetting',
        ),
        migrations.RenameModel(
            old_name='SiteConfigFont',
            new_name='SiteSettingFont',
        ),
        migrations.RenameModel(
            old_name='SiteConfigPalette',
            new_name='SiteSettingPalette',
        ),
        migrations.AlterModelOptions(
            name='sitesetting',
            options={'verbose_name': 'Site'},
        ),
        migrations.RemoveConstraint(
            model_name='sitesettingfont',
            name='unique_siteconfig_font_role',
        ),
        migrations.AddConstraint(
            model_name='sitesettingfont',
            constraint=models.UniqueConstraint(
                fields=['config', 'role'],
                name='unique_sitesetting_font_role',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='sitesettingpalette',
            name='unique_siteconfig_role',
        ),
        migrations.AddConstraint(
            model_name='sitesettingpalette',
            constraint=models.UniqueConstraint(
                fields=['config', 'role'],
                name='unique_sitesetting_role',
            ),
        ),
    ]
