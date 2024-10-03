from django.contrib.admin import SimpleListFilter


class Sender(SimpleListFilter):
    title = 'Исходящие'
    parameter_name = 'sender'

    def lookups(self, request, model_admin):
        incoming = [('Да', 'Да'),
                    ('Нет', 'Нет')]
        return incoming

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        if self.value() == "Да":
            return queryset.filter(sender_id=1)
        elif self.value() == "Нет":
            return queryset.exclude(sender_id=1)
