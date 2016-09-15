from __future__ import unicode_literals

from django.contrib import auth
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import six
import django_filters
from django_filters.filterset import FilterSetMetaclass
from rest_framework.filters import BaseFilterBackend, DjangoFilterBackend
import taggit

from nodeconductor.core import filters as core_filters
from nodeconductor.core import models as core_models
from nodeconductor.core.filters import BaseExternalFilter, UUIDFilter
from nodeconductor.logging.filters import ExternalAlertFilterBackend
from nodeconductor.structure import models
from nodeconductor.structure import serializers
from nodeconductor.structure import SupportedServices
from nodeconductor.structure.managers import filter_queryset_for_user


User = auth.get_user_model()


class ScopeTypeFilterBackend(DjangoFilterBackend):
    """ Scope filters:

        * ?scope = ``URL``
        * ?scope_type = ``string`` (can be list)
    """

    content_type_field = 'content_type'
    scope_param = 'scope_type'
    scope_models = {
        'customer': models.Customer,
        'service': models.Service,
        'project': models.Project,
        'service_project_link': models.ServiceProjectLink,
        'resource': models.ResourceMixin
    }

    @classmethod
    def get_scope_type(cls, model):
        for scope_type, scope_model in cls.scope_models.items():
            if issubclass(model, scope_model):
                return scope_type

    @classmethod
    def _get_scope_models(cls, types):
        for scope_type, scope_model in cls.scope_models.items():
            if scope_type in types:
                try:
                    for submodel in scope_model.get_all_models():
                        yield submodel
                except AttributeError:
                    yield scope_model

    @classmethod
    def _get_scope_content_types(cls, types):
        return ContentType.objects.get_for_models(*cls._get_scope_models(types)).values()

    def filter_queryset(self, request, queryset, view):
        if self.scope_param in request.query_params:
            content_types = self._get_scope_content_types(request.query_params.getlist(self.scope_param))
            return queryset.filter(**{'%s__in' % self.content_type_field: content_types})
        return queryset


class GenericRoleFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        return filter_queryset_for_user(queryset, request.user)


class CustomerFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        lookup_type='icontains',
    )
    native_name = django_filters.CharFilter(
        lookup_type='icontains',
    )
    abbreviation = django_filters.CharFilter(
        lookup_type='icontains',
    )
    contact_details = django_filters.CharFilter(
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.Customer
        fields = [
            'name',
            'abbreviation',
            'contact_details',
            'native_name',
            'registration_code',
        ]
        order_by = [
            'name',
            'abbreviation',
            'contact_details',
            'native_name',
            'registration_code',
            # desc
            '-name',
            '-abbreviation',
            '-contact_details',
            '-native_name',
            '-registration_code',
        ]


class ProjectFilter(django_filters.FilterSet):
    customer = UUIDFilter(
        name='customer__uuid',
        distinct=True,
    )

    customer_name = django_filters.CharFilter(
        name='customer__name',
        distinct=True,
        lookup_type='icontains'
    )

    customer_native_name = django_filters.CharFilter(
        name='customer__native_name',
        distinct=True,
        lookup_type='icontains'
    )

    customer_abbreviation = django_filters.CharFilter(
        name='customer__abbreviation',
        distinct=True,
        lookup_type='icontains'
    )

    project_group = UUIDFilter(
        name='project_groups__uuid',
        distinct=True,
    )

    project_group_name = django_filters.CharFilter(
        name='project_groups__name',
        distinct=True,
        lookup_type='icontains'
    )

    name = django_filters.CharFilter(lookup_type='icontains')

    description = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = models.Project
        fields = [
            'project_group',
            'project_group_name',
            'name',
            'customer', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            'description',
            'created',
        ]
        order_by = [
            'name',
            '-name',
            'created',
            '-created',
            'project_groups__name',
            '-project_groups__name',
            'customer__native_name',
            '-customer__native_name',
            'customer__name',
            '-customer__name',
            'customer__abbreviation',
            '-customer__abbreviation',
        ]

        order_by_mapping = {
            # Proper field naming
            'project_group_name': 'project_groups__name',
            'customer_name': 'customer__name',
            'customer_abbreviation': 'customer__abbreviation',
            'customer_native_name': 'customer__native_name',

            # Backwards compatibility
            'project_groups__name': 'project_groups__name',
        }


class ProjectGroupFilter(django_filters.FilterSet):
    customer = UUIDFilter(
        name='customer__uuid',
        distinct=True,
    )
    customer_name = django_filters.CharFilter(
        name='customer__name',
        distinct=True,
        lookup_type='icontains',
    )
    customer_native_name = django_filters.CharFilter(
        name='customer__native_name',
        distinct=True,
        lookup_type='icontains',
    )

    customer_abbreviation = django_filters.CharFilter(
        name='customer__abbreviation',
        distinct=True,
        lookup_type='icontains',
    )

    name = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = models.ProjectGroup
        fields = [
            'name',
            'customer',
            'customer_name',
            'customer_native_name',
            'customer_abbreviation',
        ]
        order_by = [
            'name',
            '-name',
            'customer__name',
            '-customer__name',
            'customer__native_name',
            '-customer__native_name',
            'customer__abbreviation',
            '-customer__abbreviation',
        ]
        order_by_mapping = {
            'customer_name': 'customer__name',
            'customer_abbreviation': 'customer__abbreviation',
            'customer_native_name': 'customer__native_name',
        }


class ProjectGroupMembershipFilter(django_filters.FilterSet):
    project_group = UUIDFilter(
        name='projectgroup__uuid',
    )

    project_group_name = django_filters.CharFilter(
        name='projectgroup__name',
        lookup_type='icontains',
    )

    project = UUIDFilter(
        name='project__uuid',
    )

    project_name = django_filters.CharFilter(
        name='project__name',
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.ProjectGroup.projects.through
        fields = [
            'project_group',
            'project_group_name',
            'project',
            'project_name',
        ]


class UserFilter(django_filters.FilterSet):
    project_group = django_filters.CharFilter(
        name='groups__projectrole__project__project_groups__name',
        distinct=True,
        lookup_type='icontains',
    )
    project = django_filters.CharFilter(
        name='groups__projectrole__project__name',
        distinct=True,
        lookup_type='icontains',
    )

    full_name = django_filters.CharFilter(lookup_type='icontains')
    username = django_filters.CharFilter()
    native_name = django_filters.CharFilter(lookup_type='icontains')
    job_title = django_filters.CharFilter(lookup_type='icontains')
    email = django_filters.CharFilter(lookup_type='icontains')
    is_active = django_filters.BooleanFilter()

    class Meta(object):
        model = User
        fields = [
            'full_name',
            'native_name',
            'organization',
            'organization_approved',
            'email',
            'phone_number',
            'description',
            'job_title',
            'project',
            'project_group',
            'username',
            'civil_number',
            'is_active',
        ]
        order_by = [
            'full_name',
            'native_name',
            'organization',
            'organization_approved',
            'email',
            'phone_number',
            'description',
            'job_title',
            'username',
            'is_active',
            # descending
            '-full_name',
            '-native_name',
            '-organization',
            '-organization_approved',
            '-email',
            '-phone_number',
            '-description',
            '-job_title',
            '-username',
            '-is_active',
        ]


# TODO: cover filtering/ordering with tests
class ProjectPermissionFilter(django_filters.FilterSet):
    project = UUIDFilter(
        name='group__projectrole__project__uuid',
    )
    project_url = core_filters.URLFilter(
        view_name='project-detail',
        name='group__projectrole__project__uuid',
    )
    user_url = core_filters.URLFilter(
        view_name='user-detail',
        name='user__uuid',
    )
    username = django_filters.CharFilter(
        name='user__username',
        lookup_type='exact',
    )
    full_name = django_filters.CharFilter(
        name='user__full_name',
        lookup_type='icontains',
    )
    native_name = django_filters.CharFilter(
        name='user__native_name',
        lookup_type='icontains',
    )
    role = core_filters.MappedChoiceFilter(
        name='group__projectrole__role_type',
        choices=(
            ('admin', 'Administrator'),
            ('manager', 'Manager'),
            # TODO: Removing this drops support of filtering by numeric codes
            (models.ProjectRole.ADMINISTRATOR, 'Administrator'),
            (models.ProjectRole.MANAGER, 'Manager'),
        ),
        choice_mappings={
            'admin': models.ProjectRole.ADMINISTRATOR,
            'manager': models.ProjectRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = [
            'role',
            'project',
            'username',
            'full_name',
            'native_name',
        ]
        order_by = [
            'user__username',
            'user__full_name',
            'user__native_name',
            # desc
            '-user__username',
            '-user__full_name',
            '-user__native_name',
        ]


class ProjectGroupPermissionFilter(django_filters.FilterSet):
    project_group = UUIDFilter(
        name='group__projectgrouprole__project_group__uuid',
    )
    project_group_url = core_filters.URLFilter(
        view_name='projectgroup-detail',
        name='group__projectgrouprole__project_group__uuid',
    )
    user_url = core_filters.URLFilter(
        view_name='user-detail',
        name='user__uuid',
    )
    username = django_filters.CharFilter(
        name='user__username',
        lookup_type='exact',
    )
    full_name = django_filters.CharFilter(
        name='user__full_name',
        lookup_type='icontains',
    )
    native_name = django_filters.CharFilter(
        name='user__native_name',
        lookup_type='icontains',
    )
    role = core_filters.MappedChoiceFilter(
        name='group__projectgrouprole__role_type',
        choices=(
            ('manager', 'Manager'),
            # TODO: Removing this drops support of filtering by numeric codes
            (models.ProjectGroupRole.MANAGER, 'Manager'),
        ),
        choice_mappings={
            'manager': models.ProjectGroupRole.MANAGER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = [
            'role',
            'project_group',
            'username',
            'full_name',
            'native_name',
        ]
        order_by = [
            'user__username',
            'user__full_name',
            'user__native_name',
            # desc
            '-user__username',
            '-user__full_name',
            '-user__native_name',

        ]


class CustomerPermissionFilter(django_filters.FilterSet):
    customer = UUIDFilter(
        name='group__customerrole__customer__uuid',
    )
    customer_url = core_filters.URLFilter(
        view_name='customer-detail',
        name='group__customerrole__customer__uuid',
    )
    user_url = core_filters.URLFilter(
        view_name='user-detail',
        name='user__uuid',
    )
    username = django_filters.CharFilter(
        name='user__username',
        lookup_type='exact',
    )
    full_name = django_filters.CharFilter(
        name='user__full_name',
        lookup_type='icontains',
    )
    native_name = django_filters.CharFilter(
        name='user__native_name',
        lookup_type='icontains',
    )
    role = core_filters.MappedChoiceFilter(
        name='group__customerrole__role_type',
        choices=(
            ('owner', 'Owner'),
            # TODO: Removing this drops support of filtering by numeric codes
            (models.CustomerRole.OWNER, 'Owner'),
        ),
        choice_mappings={
            'owner': models.CustomerRole.OWNER,
        },
    )

    class Meta(object):
        model = User.groups.through
        fields = [
            'role',
            'customer',
            'username',
            'full_name',
            'native_name',
        ]
        order_by = [
            'user__username',
            'user__full_name',
            'user__native_name',
            # desc
            '-user__username',
            '-user__full_name',
            '-user__native_name',

        ]


class SshKeyFilter(django_filters.FilterSet):
    uuid = UUIDFilter()
    user_uuid = UUIDFilter(name='user__uuid')
    name = django_filters.CharFilter(lookup_type='icontains')

    class Meta(object):
        model = core_models.SshPublicKey
        fields = [
            'name',
            'fingerprint',
            'uuid',
            'user_uuid'
        ]
        order_by = [
            'name',
            '-name',
        ]


class ServiceTypeFilter(django_filters.Filter):
    def filter(self, qs, value):
        value = SupportedServices.get_filter_mapping().get(value)
        return super(ServiceTypeFilter, self).filter(qs, value)


class ServiceSettingsFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_type='icontains')
    type = ServiceTypeFilter()
    state = core_filters.SynchronizationStateFilter()

    class Meta(object):
        model = models.ServiceSettings
        fields = ('name', 'type', 'state', 'shared')


class ServiceSettingsScopeFilterBackend(core_filters.GenericKeyFilterBackend):

    def get_related_models(self):
        return models.ResourceMixin.get_all_models()

    def get_field_name(self):
        return 'scope'


class ServiceFilterMetaclass(FilterSetMetaclass):
    """ Build a list of supported resource via serializers definition.
        See SupportedServices for details.
    """
    def __new__(cls, name, bases, args):
        service_filter = super(ServiceFilterMetaclass, cls).__new__(cls, name, bases, args)
        model = args['Meta'].model
        if not model._meta.abstract:
            SupportedServices.register_service_filter(args['Meta'].model, service_filter)
        return service_filter


class BaseServiceFilter(six.with_metaclass(ServiceFilterMetaclass, django_filters.FilterSet)):
    customer = UUIDFilter(name='customer__uuid')
    name = django_filters.CharFilter(lookup_type='icontains')
    project = core_filters.URLFilter(view_name='project-detail', name='projects__uuid', distinct=True)
    project_uuid = UUIDFilter(name='projects__uuid', distinct=True)
    settings = core_filters.URLFilter(view_name='servicesettings-detail', name='settings__uuid', distinct=True)
    shared = django_filters.BooleanFilter(name='settings__shared', distinct=True)
    type = ServiceTypeFilter(name='settings__type')
    tag = django_filters.ModelMultipleChoiceFilter(
        name='settings__tags__name',
        to_field_name='name',
        lookup_type='in',
        queryset=taggit.models.Tag.objects.all(),
    )
    # rtag - required tag, support for filtration by tags using AND operation
    # ?rtag=t1&rtag=t2 - will filter instances that have both t1 and t2.
    rtag = django_filters.ModelMultipleChoiceFilter(
        name='settings__tags__name',
        to_field_name='name',
        queryset=taggit.models.Tag.objects.all(),
        conjoined=True,
    )

    class Meta(object):
        model = models.Service
        fields = ('name', 'project_uuid', 'customer', 'project', 'settings', 'shared', 'type', 'tag', 'rtag')


class BaseServiceProjectLinkFilter(django_filters.FilterSet):
    service_uuid = UUIDFilter(name='service__uuid')
    customer_uuid = UUIDFilter(name='service__customer__uuid')
    project_uuid = UUIDFilter(name='project__uuid')
    project = core_filters.URLFilter(view_name='project-detail', name='project__uuid')

    class Meta(object):
        model = models.ServiceProjectLink


class ResourceFilterMetaclass(FilterSetMetaclass):
    """ Build a list of supported resource via serializers definition.
        See SupportedServices for details.
    """
    def __new__(cls, name, bases, args):
        resource_filter = super(ResourceFilterMetaclass, cls).__new__(cls, name, bases, args)
        SupportedServices.register_resource_filter(args['Meta'].model, resource_filter)
        return resource_filter


class BaseResourceFilter(six.with_metaclass(ResourceFilterMetaclass,
                         django_filters.FilterSet)):
    # customer
    customer = UUIDFilter(name='service_project_link__service__customer__uuid')
    customer_uuid = UUIDFilter(name='service_project_link__service__customer__uuid')
    customer_name = django_filters.CharFilter(
        name='service_project_link__service__customer__name', lookup_type='icontains')
    customer_native_name = django_filters.CharFilter(
        name='service_project_link__project__customer__native_name', lookup_type='icontains')
    customer_abbreviation = django_filters.CharFilter(
        name='service_project_link__project__customer__abbreviation', lookup_type='icontains')
    # project
    project = UUIDFilter(name='service_project_link__project__uuid')
    project_uuid = UUIDFilter(name='service_project_link__project__uuid')
    project_name = django_filters.CharFilter(name='service_project_link__project__name', lookup_type='icontains')
    # project group
    project_group = UUIDFilter(name='service_project_link__project__project_groups__uuid')
    project_group_uuid = UUIDFilter(name='service_project_link__project__project_groups__uuid')
    project_group_name = django_filters.CharFilter(
        name='service_project_link__project__project_groups__name', lookup_type='icontains')
    # service
    service_uuid = UUIDFilter(name='service_project_link__service__uuid')
    service_name = django_filters.CharFilter(name='service_project_link__service__name', lookup_type='icontains')
    # service settings
    service_settings_uuid = UUIDFilter(name='service_project_link__service__settings__uuid')
    service_settings_name = django_filters.CharFilter(name='service_project_link__service__settings__name',
                                                      lookup_type='icontains')
    # resource
    name = django_filters.CharFilter(lookup_type='icontains')
    description = django_filters.CharFilter(lookup_type='icontains')
    state = core_filters.MappedMultipleChoiceFilter(
        choices=[(representation, representation) for db_value, representation in models.Resource.States.CHOICES],
        choice_mappings={representation: db_value for db_value, representation in models.Resource.States.CHOICES},
    )
    uuid = UUIDFilter(lookup_type='exact')
    tag = django_filters.ModelMultipleChoiceFilter(
        name='tags__name',
        to_field_name='name',
        lookup_type='in',
        queryset=taggit.models.Tag.objects.all(),
    )
    rtag = django_filters.ModelMultipleChoiceFilter(
        name='tags__name',
        to_field_name='name',
        queryset=taggit.models.Tag.objects.all(),
        conjoined=True,
    )

    strict = False

    class Meta(object):
        model = models.ResourceMixin
        fields = (
            # customer
            'customer', 'customer_uuid', 'customer_name', 'customer_native_name', 'customer_abbreviation',
            # project
            'project', 'project_uuid', 'project_name',
            # project group
            'project_group', 'project_group_uuid', 'project_group_name',
            # service
            'service_uuid', 'service_name',
            # service settings
            'service_settings_name', 'service_settings_uuid',
            # resource
            'name', 'description', 'state', 'uuid', 'tag', 'rtag',
        )
        order_by = [
            'name',
            '-name',
            'state',
            '-state',
            'service_project_link__project__customer__name',
            '-service_project_link__project__customer__name',
            'service_project_link__project__customer__native_name',
            '-service_project_link__project__customer__native_name',
            'service_project_link__project__customer__abbreviation',
            '-service_project_link__project__customer__abbreviation',
            'service_project_link__project__name',
            '-service_project_link__project__name',
            'service_project_link__project__project_groups__name',
            '-service_project_link__project__project_groups__name',
            'created',
            '-created',
        ]
        order_by_mapping = {
            'customer_name': 'service_project_link__project__customer__name',
            'customer_native_name': 'service_project_link__project__customer__native_name',
            'customer_abbreviation': 'service_project_link__project__customer__abbreviation',
            'project_name': 'service_project_link__project__name',
            'project_group_name': 'service_project_link__project__project_groups__name',
        }


# XXX: use single class when NC-1237 is done
class BaseResourceStateFilter(BaseResourceFilter):

    state = core_filters.MappedMultipleChoiceFilter(
        choices=[(representation, representation) for db_value, representation in core_models.StateMixin.States.CHOICES],
        choice_mappings={representation: db_value for db_value, representation in core_models.StateMixin.States.CHOICES},
    )

    class Meta(BaseResourceFilter.Meta):
        model = models.ResourceMixin


class TagsFilter(BaseFilterBackend):
    """ Tags ordering. Filtering for complex tags.

    Example:
        ?tag__license-os=centos7 - will filter objects with tag "license-os:centos7".

    Allow to define next parameters in view:
     - tags_filter_db_field - name of tags field in database. Default: tags.
     - tags_filter_request_field - name of tags in request. Default: tag.
    """

    def filter_queryset(self, request, queryset, view):
        self.db_field = getattr(view, 'tags_filter_db_field', 'tags')
        self.request_field = getattr(view, 'tags_filter_request_field', 'tag')

        queryset = self._filter(request, queryset)
        queryset = self._order(request, queryset)
        return queryset

    def _filter(self, request, queryset):
        for key in request.query_params.keys():
            item_name = self._get_item_name(key)
            if item_name:
                value = request.query_params.get(key)
                filter_kwargs = {
                    self.db_field + '__name__startswith': item_name,
                    self.db_field + '__name__icontains': value,
                }
                queryset = queryset.filter(**filter_kwargs)
        return queryset

    def _order(self, request, queryset):
        order_by = request.query_params.get('o')
        item_name = self._get_item_name(order_by)
        if item_name:
            filter_kwargs = {self.db_field + '__name__startswith': item_name}
            queryset = queryset.filter(**filter_kwargs).order_by(self.db_field + '__name')
        return queryset

    def _get_item_name(self, key):
        prefix = self.request_field + '__'
        if key and key.startswith(prefix):
            return key[len(prefix):]


class StartTimeFilter(BaseFilterBackend):
    """
    In PostgreSQL NULL values come *last* with ascending sort order.
    In MySQL NULL values come *first* with ascending sort order.
    This filter provides unified sorting for both databases.
    """
    def filter_queryset(self, request, queryset, view):
        order = request.query_params.get('o', None)
        if order == 'start_time':
            queryset = queryset.extra(select={
                'is_null': 'CASE WHEN start_time IS NULL THEN 0 ELSE 1 END'}) \
                .order_by('is_null', 'start_time')
        elif order == '-start_time':
            queryset = queryset.extra(select={
                'is_null': 'CASE WHEN start_time IS NULL THEN 0 ELSE 1 END'}) \
                .order_by('-is_null', '-start_time')

        return queryset


class BaseServicePropertyFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        name='name',
        lookup_type='icontains',
    )

    class Meta(object):
        model = models.BaseServiceProperty
        fields = ('name',)


class ServicePropertySettingsFilter(BaseServicePropertyFilter):
    settings_uuid = UUIDFilter(name='settings__uuid')
    settings = core_filters.URLFilter(view_name='servicesettings-detail', name='settings__uuid', distinct=True)

    class Meta(BaseServicePropertyFilter.Meta):
        fields = BaseServicePropertyFilter.Meta.fields + ('settings_uuid', 'settings')


class AggregateFilter(BaseExternalFilter):
    """
    Filter by aggregate
    """

    def filter(self, request, queryset, view):
        # Don't apply filter if aggregate is not specified
        if 'aggregate' not in request.query_params:
            return queryset

        serializer = serializers.AggregateSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        aggregates = serializer.get_aggregates(request.user)
        projects = serializer.get_projects(request.user)
        querysets = [aggregates, projects]
        aggregates_ids = list(aggregates.values_list('id', flat=True))
        query = {serializer.data['aggregate'] + '__in': aggregates_ids}

        all_models = (models.ResourceMixin.get_all_models() +
                      models.ServiceProjectLink.get_all_models())

        if serializer.data['aggregate'] == 'customer':
            all_models += models.Service.get_all_models()

        for model in all_models:
            qs = model.objects.filter(**query).all()
            querysets.append(filter_queryset_for_user(qs, request.user))

        aggregate_query = Q()
        for qs in querysets:
            content_type = ContentType.objects.get_for_model(qs.model)
            ids = qs.values_list('id', flat=True)
            aggregate_query |= Q(content_type=content_type, object_id__in=ids)

        return queryset.filter(aggregate_query)

ExternalAlertFilterBackend.register(AggregateFilter())


class SummaryFilter(core_filters.DjangoMappingFilterBackend):
    """ Base filter for summary querysets """

    def filter_queryset(self, request, queryset, view):
        queryset = self.filter(request, queryset, view)
        queryset = self.order(request, queryset, view)
        return queryset

    def get_queryset_filter(self, queryset):
        """ Return specific for queryset filter if it exists """
        raise NotImplementedError()

    def get_base_filter(self):
        """ Return base filter that could be used for all summary objects """
        raise NotImplementedError()

    def _get_filter(self, queryset):
        try:
            return self.get_queryset_filter(queryset)
        except NotImplementedError:
            return self.get_base_filter()

    def filter(self, request, queryset, view):
        """ Filter each resource separately using its own filter """
        summary_queryset = queryset
        filtered_querysets = []
        for queryset in summary_queryset.querysets:
            filter_class = self._get_filter(queryset)
            queryset = filter_class(request.query_params, queryset=queryset).qs
            filtered_querysets.append(queryset)

        summary_queryset.querysets = filtered_querysets
        return summary_queryset

    def order(self, request, queryset, view):
        """ Order all resources together using BaseResourceFilter """
        base_filter = self.get_base_filter()
        ordering = self.get_valid_ordering(request, base_filter)
        if ordering:
            queryset = queryset.order_by(ordering)
        return queryset


class ResourceSummaryFilterBackend(SummaryFilter):
    """ Filter and order SummaryQuerySet of resources """

    def get_queryset_filter(self, queryset):
        try:
            return SupportedServices.get_resource_filter(queryset.model)
        except KeyError:
            return super(ResourceSummaryFilterBackend, self).get_queryset_filter(queryset)

    def get_base_filter(self):
        return BaseResourceFilter


class ServiceSummaryFilterBackend(SummaryFilter):

    def get_queryset_filter(self, queryset):
        try:
            return SupportedServices.get_service_filter(queryset.model)
        except KeyError:
            return super(ServiceSummaryFilterBackend, self).get_queryset_filter(queryset)

    def get_base_filter(self):
        return BaseServiceFilter
