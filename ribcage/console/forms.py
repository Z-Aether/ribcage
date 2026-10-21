from django import forms


class BackupCodeForm(forms.Form):
    # Only ever in the post's body, so the code never reaches an address or the access log (#16, #68).
    code = forms.CharField(label="Code", strip=True, widget=forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false", "autofocus": True}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, label_suffix="", **kwargs)
