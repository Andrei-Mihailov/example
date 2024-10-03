from django import forms
from django.forms.widgets import TextInput
from django.contrib.admin import widgets
from django.contrib.admin.helpers import ActionForm

from .models import ColorsEvent


class XForm(ActionForm):
    date_remove = forms.DateField(label='Дата удаления из базы:',
                                  required=False,
                                  widget=widgets.AdminDateWidget(format='%d.%m.%Y'),
                                  input_formats=('%d.%m.%Y',))

    class Media:
        css = {
            'all': ('admin/css/widgets.css',)
        }


def rgb_to_hex(rgb):
    r, g, b = map(int, rgb.split(","))
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


class ColorsForm(forms.ModelForm):
    theme_name = forms.ModelChoiceField(
        label="Название темы",
        queryset=ColorsEvent.objects.values_list('theme_name', flat=True).distinct(),
        to_field_name='theme_name'
    )

    class Meta:
        model = ColorsEvent
        fields = [
            'group_event',
            'theme_name',
            'color_main',
            'color_start',
            'color_end',
        ]
        widgets = {
            "color_main": TextInput(attrs={"type": "color"}),
            "color_start": TextInput(attrs={"type": "color"}),
            "color_end": TextInput(attrs={"type": "color"})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        theme_choices = ColorsEvent.objects.values_list('theme_name', flat=True).distinct()
        self.fields['theme_name'].choices = [(theme, theme) for theme in theme_choices]

        if self.instance and self.instance.pk:
            instance_color = ColorsEvent.objects.get(id=self.instance.pk)
            self.initial['color_main'] = rgb_to_hex(instance_color.color_main)
            self.initial['color_start'] = rgb_to_hex(instance_color.color_start)
            self.initial['color_end'] = rgb_to_hex(instance_color.color_end)

    def clean(self):
        cleaned_data = super().clean()
        theme_name = cleaned_data.get('theme_name')

        if theme_name:
            try:
                old_color = ColorsEvent.objects.filter(theme_name=self.initial['theme_name']).first()
                old_color.group_event = None
                old_color.save()
                color_event_instance = ColorsEvent.objects.get(theme_name=theme_name)
                cleaned_data['color_main'] = color_event_instance.color_main
                cleaned_data['color_start'] = color_event_instance.color_start
                cleaned_data['color_end'] = color_event_instance.color_end
                self.instance = color_event_instance
            except ColorsEvent.DoesNotExist:
                self.add_error('theme_name', "Выбранная тема не существует.")

        return cleaned_data
