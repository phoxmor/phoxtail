from wagtail.admin.panels import FieldPanel


class CodeEditorPanel(FieldPanel):
    class BoundPanel(FieldPanel.BoundPanel):
        template_name = "admin/panels/code_editor/monaco.html"

        class Media:
            js = [
                "phoxtail_streams/admin/panels/code_editor/monaco/js/loader.js",
                "phoxtail_streams/admin/panels/code_editor/monaco/js/main.js",
            ]
            css = {
                "all": ["phoxtail_streams/admin/panels/code_editor/monaco/css/main.css"]
            }
