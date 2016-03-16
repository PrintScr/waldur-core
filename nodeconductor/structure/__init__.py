import collections
import importlib

from django.conf import settings
from django.utils.lru_cache import lru_cache
from django.utils.encoding import force_text
from rest_framework.reverse import reverse

from nodeconductor.core.utils import sort_dict

default_app_config = 'nodeconductor.structure.apps.StructureConfig'


class SupportedServices(object):
    """ Comprehensive list of currently supported services and resources.
        Build the list via serializers definition on application start.
        Example data structure of registry:

        {
            'gitlab': {
                'name': 'GitLab',
                'model_name': 'gitlab.gitlabservice',
                'backend': nodeconductor_plus.gitlab.backend.GitLabBackend,
                'detail_view': 'gitlab-detail',
                'list_view': 'gitlab-list',
                'properties': {},
                'resources': {
                    'gitlab.group': {
                        'name': 'Group',
                        'detail_view': 'gitlab-group-detail',
                        'list_view': 'gitlab-group-list'
                    },
                    'gitlab.project': {
                        'name': 'Project',
                        'detail_view': 'gitlab-project-detail',
                        'list_view': 'gitlab-project-list'
                    }
                }
            }
        }

    """

    class Types(object):
        OpenStack = 'OpenStack'
        IaaS = 'IaaS'

        @classmethod
        def get_direct_filter_mapping(cls):
            return tuple((name, name) for _, name in SupportedServices.get_choices())

        @classmethod
        def get_reverse_filter_mapping(cls):
            return {name: code for code, name in SupportedServices.get_choices()}

    _registry = collections.defaultdict(lambda: {
        'backend': None,
        'resources': {},
        'properties': {}
    })

    @classmethod
    def register_backend(cls, backend_class, nested=False):
        if not cls._is_active_model(backend_class):
            return

        # For nested backends just discover resources/properties
        if not nested:
            key = cls.get_model_key(backend_class)
            cls._registry[key]['backend'] = backend_class

        # Forcely import service serialize to run services autodiscovery
        try:
            module_name = backend_class.__module__
            importlib.import_module(module_name.replace('backend', 'serializers'))
        except ImportError:
            pass

    @classmethod
    def register_service(cls, model):
        if model is NotImplemented or not cls._is_active_model(model):
            return
        key = cls.get_model_key(model)
        cls._registry[key]['name'] = key
        cls._registry[key]['model_name'] = cls._get_model_str(model)
        cls._registry[key]['detail_view'] = cls.get_detail_view_for_model(model)
        cls._registry[key]['list_view'] = cls.get_list_view_for_model(model)

    @classmethod
    def register_resource_serializer(cls, model, serializer):
        if model is NotImplemented or not cls._is_active_model(model):
            return
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        cls._registry[key]['resources'].setdefault(model_str, {'name': model.__name__})
        cls._registry[key]['resources'][model_str]['detail_view'] = cls.get_detail_view_for_model(model)
        cls._registry[key]['resources'][model_str]['list_view'] = cls.get_list_view_for_model(model)
        cls._registry[key]['resources'][model_str]['serializer'] = serializer

    @classmethod
    def register_resource_filter(cls, model, filter):
        if model is NotImplemented or not cls._is_active_model(model) or model._meta.abstract:
            return
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        cls._registry[key]['resources'].setdefault(model_str, {'name': model.__name__})
        cls._registry[key]['resources'][model_str]['filter'] = filter

    @classmethod
    def register_resource_view(cls, model, view):
        if model is NotImplemented or not cls._is_active_model(model) or model._meta.abstract:
            return
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        cls._registry[key]['resources'].setdefault(model_str, {'name': model.__name__})
        cls._registry[key]['resources'][model_str]['view'] = view

    @classmethod
    def register_property(cls, model):
        if model is NotImplemented or not cls._is_active_model(model):
            return
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        cls._registry[key]['properties'][model_str] = {
            'name': model.__name__,
            'list_view': cls.get_list_view_for_model(model)
        }

    @classmethod
    def get_service_backend(cls, key):
        try:
            return cls._registry[key]['backend']
        except IndexError:
            raise ServiceBackendNotImplemented

    @classmethod
    def get_services(cls, request=None):
        """ Get a list of services endpoints.
            {
                "Oracle": "/api/oracle/",
                "OpenStack": "/api/openstack/",
                "GitLab": "/api/gitlab/",
                "DigitalOcean": "/api/digitalocean/"
            }
        """
        return {service['name']: reverse(service['list_view'], request=request)
                for service in cls._registry.values()}

    @classmethod
    def get_resources(cls, request=None):
        """ Get a list of resources endpoints.
            {
                "IaaS.Instance": "/api/iaas-resources/",
                "DigitalOcean.Droplet": "/api/digitalocean-droplets/",
                "Oracle.Database": "/api/oracle-databases/",
                "GitLab.Group": "/api/gitlab-groups/",
                "GitLab.Project": "/api/gitlab-projects/"
            }
        """
        return {'.'.join([service['name'], resource['name']]): reverse(resource['list_view'], request=request)
                for service in cls._registry.values()
                for resource in service['resources'].values()}

    @classmethod
    def get_resource_serializer(cls, model):
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        return cls._registry[key]['resources'][model_str]['serializer']

    @classmethod
    def get_resource_filter(cls, model):
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        return cls._registry[key]['resources'][model_str]['filter']

    @classmethod
    def get_resource_view(cls, model):
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        return cls._registry[key]['resources'][model_str]['view']

    @classmethod
    def get_resource_actions(cls, model):
        view = cls.get_resource_view(model)
        actions = {}
        for key in dir(view):
            attr = getattr(view, key)
            if hasattr(attr, 'bind_to_methods') and 'post' in attr.bind_to_methods:
                actions[key] = attr
        actions['destroy'] = view.destroy
        return sort_dict(actions)

    @classmethod
    def get_services_with_resources(cls, request=None):
        """ Get a list of services and resources endpoints.
            {
                ...
                "GitLab": {
                    "url": "/api/gitlab/",
                    "service_project_link_url": "/api/gitlab-service-project-link/",
                    "resources": {
                        "Project": "/api/gitlab-projects/",
                        "Group": "/api/gitlab-groups/"
                    }
                },
                ...
            }
        """
        from django.apps import apps

        data = {}
        for service in cls._registry.values():
            service_model = apps.get_model(service['model_name'])
            service_project_link = cls.get_service_project_link(service_model)
            service_project_link_url = reverse(cls.get_list_view_for_model(service_project_link), request=request)

            data[service['name']] = {
                'url': reverse(service['list_view'], request=request),
                'service_project_link_url': service_project_link_url,
                'resources': {resource['name']: reverse(resource['list_view'], request=request)
                              for resource in service['resources'].values()},
                'properties': {resource['name']: reverse(resource['list_view'], request=request)
                               for resource in service.get('properties', {}).values()}
            }
        return data

    @classmethod
    @lru_cache(maxsize=1)
    def get_service_models(cls):
        """ Get a list of service models.
            {
                ...
                'gitlab': {
                    "service": nodeconductor_plus.gitlab.models.GitLabService,
                    "service_project_link": nodeconductor_plus.gitlab.models.GitLabServiceProjectLink,
                    "resources": [
                        nodeconductor_plus.gitlab.models.Group,
                        nodeconductor_plus.gitlab.models.Project
                    ],
                },
                ...
            }

        """
        from django.apps import apps

        data = {}
        for key, service in cls._registry.items():
            service_model = apps.get_model(service['model_name'])
            service_project_link = cls.get_service_project_link(service_model)
            data[key] = {
                'service': service_model,
                'service_project_link': service_project_link,
                'resources': [apps.get_model(r) for r in service['resources'].keys()],
                'properties': [apps.get_model(r) for r in service['properties'].keys() if '.' in r],
            }

        return data

    @classmethod
    def get_service_project_link(cls, service_model):
        return next(m.related_model for m in service_model._meta.get_all_related_objects()
                    if m.name == 'cloudprojectmembership' or m.name.endswith('serviceprojectlink'))

    @classmethod
    @lru_cache(maxsize=1)
    def get_resource_models(cls):
        """ Get a list of resource models.
            {
                'DigitalOcean.Droplet': nodeconductor_plus.digitalocean.models.Droplet,
                'GitLab.Group': nodeconductor_plus.gitlab.models.Group,
                'GitLab.Project': nodeconductor_plus.gitlab.models.Project,
                'IaaS.Instance': nodeconductor.iaas.models.Instance,
                'Oracle.Database': nodeconductor_oracle_dbaas.models.Database
            }

        """
        from django.apps import apps

        return {'.'.join([service['name'], attrs['name']]): apps.get_model(resource)
                for service in cls._registry.values()
                for resource, attrs in service['resources'].items()}

    @classmethod
    @lru_cache(maxsize=1)
    def get_service_resources(cls, model):
        from django.apps import apps

        key = cls.get_model_key(model)
        resources = cls._registry[key]['resources'].keys()
        return [apps.get_model(resource) for resource in resources]

    @classmethod
    def get_name_for_model(cls, model):
        """ Get a name for given class or model:
            -- it's a service type for a service
            -- it's a <service_type>.<resource_model_name> for a resource
        """
        key = cls.get_model_key(model)
        model_str = cls._get_model_str(model)
        service = cls._registry[key]
        if model_str in service['resources']:
            return '{}.{}'.format(service['name'], service['resources'][model_str]['name'])
        else:
            return service['name']

    @classmethod
    def get_related_models(cls, model):
        """ Get a dictionary with related structure models for given class or model:

            >> SupportedServices.get_related_models(gitlab_models.Project)
            {
                'service': nodeconductor_plus.gitlab.models.GitLabService,
                'service_project_link': nodeconductor_plus.gitlab.models.GitLabServiceProjectLink,
                'resources': [
                    nodeconductor_plus.gitlab.models.Group,
                    nodeconductor_plus.gitlab.models.Project,
                ]
            }
        """
        model_str = cls._get_model_str(model)
        for models in cls.get_service_models().values():
            if model_str == cls._get_model_str(models['service']) or \
               model_str == cls._get_model_str(models['service_project_link']):
                return models

            for resource_model in models['resources']:
                if model_str == cls._get_model_str(resource_model):
                    return models

    @classmethod
    def _is_active_model(cls, model):
        """ Check is model app name is in list of INSTALLED_APPS """
        # We need to use such tricky way to check because of inconsistent apps names:
        # some apps are included in format "<module_name>.<app_name>" like "nodeconductor.openstack"
        # other apps are included in format "<app_name>" like "nodecondcutor_sugarcrm"
        return ('.'.join(model.__module__.split('.')[:2]) in settings.INSTALLED_APPS or
                '.'.join(model.__module__.split('.')[:1]) in settings.INSTALLED_APPS)

    @classmethod
    def _get_model_str(cls, model):
        return force_text(model._meta)

    @classmethod
    def get_model_key(cls, model):
        from django.apps import apps
        return apps.get_containing_app_config(model.__module__).service_name

    @classmethod
    def get_list_view_for_model(cls, model):
        return model.get_url_name() + '-list'

    @classmethod
    def get_detail_view_for_model(cls, model):
        return model.get_url_name() + '-detail'

    @classmethod
    @lru_cache(maxsize=1)
    def get_choices(cls):
        items = [(code, service['name']) for code, service in cls._registry.items()]
        return sorted(items, key=lambda (code, name): name)

    @classmethod
    def has_service_type(cls, service_type):
        return service_type in cls._registry

    @classmethod
    def get_name_for_type(cls, service_type):
        try:
            return cls._registry[service_type]['name']
        except KeyError:
            return service_type


class ServiceBackendError(Exception):
    """ Base exception for errors occurring during backend communication. """
    pass


class ServiceBackendNotImplemented(NotImplementedError):
    pass


class ServiceBackend(object):
    """ Basic service backed with only common methods pre-defined. """

    def __init__(self, settings, **kwargs):
        pass

    def ping(self, raise_exception=False):
        raise ServiceBackendNotImplemented

    def ping_resource(self, resource):
        raise ServiceBackendNotImplemented

    def sync(self):
        raise ServiceBackendNotImplemented

    def sync_quotas(self, service_project_link):
        raise ServiceBackendNotImplemented

    def sync_link(self, service_project_link, is_initial=False):
        raise ServiceBackendNotImplemented

    def remove_link(self, service_project_link):
        raise ServiceBackendNotImplemented

    def provision(self, resource, *args, **kwargs):
        raise ServiceBackendNotImplemented

    def destroy(self, resource, force=False):
        raise ServiceBackendNotImplemented

    def stop(self, resource):
        raise ServiceBackendNotImplemented

    def start(self, resource):
        raise ServiceBackendNotImplemented

    def restart(self, resource):
        raise ServiceBackendNotImplemented

    def add_ssh_key(self, ssh_key, service_project_link):
        raise ServiceBackendNotImplemented

    def remove_ssh_key(self, ssh_key, service_project_link):
        raise ServiceBackendNotImplemented

    def add_user(self, user, service_project_link):
        raise ServiceBackendNotImplemented

    def remove_user(self, user, service_project_link):
        raise ServiceBackendNotImplemented

    def get_resources_for_import(self):
        raise ServiceBackendNotImplemented

    def get_managed_resources(self):
        raise ServiceBackendNotImplemented

    def get_monthly_cost_estimate(self, resource):
        raise ServiceBackendNotImplemented

    @staticmethod
    def gb2mb(val):
        return int(val * 1024) if val else 0

    @staticmethod
    def tb2mb(val):
        return int(val * 1024 * 1024) if val else 0

    @staticmethod
    def mb2gb(val):
        return val / 1024 if val else 0

    @staticmethod
    def mb2tb(val):
        return val / 1024 / 1024 if val else 0
