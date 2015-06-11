from django.contrib.contenttypes import models as ct_models
from django.db import models
from django.db.models import Q


class QuotaManager(models.Manager):

    def filtered_for_user(self, user, queryset=None):
        from nodeconductor.quotas import utils

        if queryset is None:
            queryset = self.get_queryset()
        # XXX: This circular dependency will be removed then filter_queryset_for_user
        # will be moved to model manager method
        from nodeconductor.structure.filters import filter_queryset_for_user

        quota_scope_models = utils.get_models_with_quotas()
        query = Q()
        for model in quota_scope_models:
            user_object_ids = filter_queryset_for_user(model.objects.all(), user).values_list('id', flat=True)
            content_type_id = ct_models.ContentType.objects.get_for_model(model).id
            query |= Q(object_id__in=user_object_ids, content_type_id=content_type_id)

        return queryset.filter(query)

    def for_object(self, obj):
        kwargs = dict(
            content_type=ct_models.ContentType.objects.get_for_model(obj._meta.model),
            object_id=obj.id
        )
        return self.get_queryset().filter(**kwargs)
