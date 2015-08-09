from django.shortcuts import redirect
from django.conf.urls import patterns, url
from django.core.urlresolvers import reverse
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from nodeconductor.core.tasks import send_task
from nodeconductor.cost_tracking import models
from nodeconductor.structure import models as structure_models, admin as structure_admin


def _get_content_type_queryset(models_list):
    """ Get list of services content types """
    content_type_ids = {c.id for c in ContentType.objects.get_for_models(*models_list).values()}
    return ContentType.objects.filter(id__in=content_type_ids)


class PriceListItemAdmin(admin.ModelAdmin):
    list_display = ('uuid', 'item_type', 'key', 'value', 'units', 'service')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "content_type":
            kwargs["queryset"] = _get_content_type_queryset(structure_models.Service.get_all_models())
        return super(PriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class DefaultPriceListItemAdmin(structure_admin.ChangeReadonlyMixin, admin.ModelAdmin):
    list_display = ('uuid', 'item_type', 'key', 'value', 'units', 'resource_content_type')
    list_filter = ['item_type', 'key']
    change_readonly_fields = ('resource_content_type',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "resource_content_type":
            kwargs["queryset"] = _get_content_type_queryset(structure_models.Resource.get_all_models())
        return super(DefaultPriceListItemAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_urls(self):
        my_urls = patterns('', url(r'^sync/$', self.admin_site.admin_view(self.sync)))
        return my_urls + super(DefaultPriceListItemAdmin, self).get_urls()

    def sync(self, request):
        send_task('billing', 'sync_pricelist')()
        self.message_user(request, "Pricelists scheduled for sync")
        return redirect(reverse('admin:cost_tracking_defaultpricelistitem_changelist'))


admin.site.register(models.PriceListItem, PriceListItemAdmin)
admin.site.register(models.DefaultPriceListItem, DefaultPriceListItemAdmin)