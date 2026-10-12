from django import forms

from ribcage.hello.models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["text"]
        labels = {"text": "Message"}
