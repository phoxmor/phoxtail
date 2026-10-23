from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailTranslationsConfig(PhoxtailAppConfig):
    """phoxtail's translations: its own sentences, and its corrections to other packages'.

    Django takes a sentence's translation from the first installed app that
    has it, so core asks for this app and the wiring puts it first.
    """

    name = "phoxtail.translations"
    label = "phoxtail_translations"
    verbose_name = "Phoxtail Translations"
