from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Extract thumbnails (and probe metadata) for videos that are missing them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-generate even for videos that already have a thumbnail.",
        )

    def handle(self, *args, **options):
        from wagtailmedia.models import get_media_model

        from phoxtail.media.signals import _process_media

        Media = get_media_model()
        qs = Media.objects.filter(type="video")
        if not options["force"]:
            qs = qs.filter(thumbnail="")

        total = qs.count()
        if total == 0:
            self.stdout.write("No videos to process.")
            return

        ok = 0
        for m in qs.iterator():
            if options["force"] and m.thumbnail:
                m.thumbnail.delete(save=False)
                m.thumbnail = ""
            try:
                _process_media(m)
                self.stdout.write(f"  [ok] pk={m.pk} {m.title}")
                ok += 1
            except Exception as exc:
                self.stderr.write(f"  [fail] pk={m.pk} {m.title}: {exc}")

        self.stdout.write(self.style.SUCCESS(f"{ok}/{total} thumbnails generated."))
