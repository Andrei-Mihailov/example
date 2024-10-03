from django.contrib.admin.helpers import ActionForm
from django import forms


class ReplyEmailForm(ActionForm):
    subject = forms.CharField(widget=forms.Textarea({"rows": "1"}))
    message = forms.CharField(widget=forms.Textarea({"rows": "1"}))

    class Media:
        css = {
            'all': ('admin/css/widgets.css',)
        }
