# -*- coding: utf-8 -*-
from __future__ import absolute_import

import logging

from celery import shared_task, current_app

from nodeconductor.core.log import EventLoggerAdapter
from nodeconductor.core.tasks import transition
from nodeconductor.core.models import SynchronizationStates
from nodeconductor.iaas.backend import CloudBackendError
from nodeconductor.iaas.tasks import openstack_create_session
from nodeconductor.iaas.models import Cloud

logger = logging.getLogger(__name__)
event_logger = EventLoggerAdapter(logger)


@shared_task(name='nodeconductor.iaas.sync_services')
def sync_services(service_uuids=None):
    services = Cloud.objects.filter(state=SynchronizationStates.IN_SYNC)
    if service_uuids and isinstance(service_uuids, (list, tuple)):
        services = services.filter(uuid__in=service_uuids)

    for service in services:
        service.schedule_syncing()
        service.save()

        service_uuid = service.uuid.hex
        sync_service.apply_async(
            args=(service_uuid,),
            link=sync_service_succeeded.si(service_uuid),
            link_error=sync_service_log_error.s(service_uuid),
        )


@shared_task(name='nodeconductor.iaas.sync_service')
@transition(Cloud, 'begin_syncing')
def sync_service(service_uuid, transition_entity=None):
    cloud = transition_entity
    # TODO: Move it from OpenStackBackend to iaas.tasks.openstack
    backend = cloud.get_backend()
    backend.pull_cloud_account(cloud)


@shared_task
@transition(Cloud, 'set_in_sync')
def sync_service_succeeded(service_uuid, transition_entity=None):
    pass


@shared_task
@transition(Cloud, 'set_erred')
def sync_service_failed(service_uuid, transition_entity=None):
    pass


@shared_task
def sync_service_log_error(task_uuid, service_uuid):
    result = current_app.AsyncResult(task_uuid)
    cloud = Cloud.objects.get(uuid=service_uuid)
    event_logger.error(
        'Cloud service %s has failed to sync with error: %s.', cloud.name, result.result,
        extra={'cloud': cloud, 'event_type': 'iaas_service_sync_failed'},
    )

    sync_service_failed.delay(service_uuid)


@shared_task(name='nodeconductor.iaas.recover_erred_services')
def recover_erred_services(service_uuids=None):
    services = Cloud.objects.filter(state=SynchronizationStates.ERRED)

    if service_uuids and isinstance(service_uuids, (list, tuple)):
        services = services.filter(uuid__in=service_uuids)

    for service in services:
        service_uuid = service.uuid.hex
        recover_erred_service.delay(service_uuid)


@shared_task(name='nodeconductor.iaas.recover_erred_service')
def recover_erred_service(service_uuid):
    cloud = Cloud.objects.get(uuid=service_uuid)
    backend = cloud.get_backend()

    try:
        backend.create_admin_session(cloud.auth_url)

        cloud.state = SynchronizationStates.IN_SYNC
        cloud.save()
        logger.info('Cloud service %s has been recovered.' % cloud.name)
    except CloudBackendError:
        logger.warning('Failed to recover cloud service %s.' % cloud.name)
