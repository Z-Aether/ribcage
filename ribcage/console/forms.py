from django import forms

from ribcage.identity.forms import BareLabels

CODE_ATTRIBUTES = {"autocomplete": "off", "spellcheck": "false"}


class BackupCodeForm(BareLabels, forms.Form):
    # Only ever in the post's body, so the code never reaches an address or the access log (#16, #68).
    code = forms.CharField(label="Code", strip=True, widget=forms.TextInput(attrs={**CODE_ATTRIBUTES, "autofocus": True}))


class BackupUploadForm(BareLabels, forms.Form):
    code = forms.CharField(label="Code", strip=True, widget=forms.TextInput(attrs=CODE_ATTRIBUTES))
    backup = forms.FileField(label="Backup", widget=forms.FileInput(attrs={"accept": ".sqlite3"}))

    def __init__(self, *args, **kwargs):
        # Its own ids, beside the download form's on the same page (#81).
        super().__init__(*args, auto_id="id_upload_%s", **kwargs)
