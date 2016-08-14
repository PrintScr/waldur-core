from ddt import ddt, data
from rest_framework import status

from nodeconductor.structure.tests import factories as structure_factories

from .. import models
from . import factories
from .base_test import BaseCostTrackingTest


@ddt
class PriceEstimateListTest(BaseCostTrackingTest):

    def setUp(self):
        super(PriceEstimateListTest, self).setUp()

        self.link_price_estimate = factories.PriceEstimateFactory(
            year=2012, month=10, scope=self.service_project_link, is_manually_input=True)
        self.project_price_estimate = factories.PriceEstimateFactory(scope=self.project, year=2015, month=7)

    @data('owner', 'manager', 'administrator')
    def test_user_can_see_price_estimate_for_his_project(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.project_price_estimate.uuid.hex, [obj['uuid'] for obj in response.data])

    @data('owner', 'manager', 'administrator')
    def test_user_cannot_see_price_estimate_for_not_his_project(self, user):
        other_price_estimate = factories.PriceEstimateFactory()

        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(other_price_estimate.uuid.hex, [obj['uuid'] for obj in response.data])

    def test_user_can_filter_price_estimate_by_scope(self):
        self.client.force_authenticate(self.users['owner'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'scope': structure_factories.ProjectFactory.get_url(self.project)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.project_price_estimate.uuid.hex)

    def test_user_can_filter_price_estimates_by_date(self):
        self.client.force_authenticate(self.users['administrator'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'date': '{}.{}'.format(self.link_price_estimate.year, self.link_price_estimate.month)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.link_price_estimate.uuid.hex)

    def test_user_can_filter_price_estimates_by_date_range(self):
        self.client.force_authenticate(self.users['manager'])
        response = self.client.get(
            factories.PriceEstimateFactory.get_list_url(),
            data={'start': '{}.{}'.format(self.link_price_estimate.year, self.link_price_estimate.month + 1),
                  'end': '{}.{}'.format(self.project_price_estimate.year, self.project_price_estimate.month + 1)})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['uuid'], self.project_price_estimate.uuid.hex)

    def test_user_receive_error_on_filtering_by_not_visible_for_him_object(self):
        data = {'scope': structure_factories.ProjectFactory.get_url()}

        self.client.force_authenticate(self.users['administrator'])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url(), data=data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@ddt
class PriceEstimateCreateTest(BaseCostTrackingTest):

    def setUp(self):
        super(PriceEstimateCreateTest, self).setUp()

        self.valid_data = {
            'scope': structure_factories.TestServiceProjectLinkFactory.get_url(self.service_project_link),
            'total': 100,
            'details': {'ram': 50, 'disk': 50},
            'month': 7,
            'year': 2015,
        }

    @data('owner', 'staff')
    def test_user_can_create_price_estimate(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceEstimateFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(models.PriceEstimate.objects.filter(
            scope=self.service_project_link,
            is_manually_input=True,
            month=self.valid_data['month'],
            year=self.valid_data['year'],
            is_visible=True).exists()
        )

    @data('manager', 'administrator')
    def test_user_without_permissions_can_not_create_price_estimate(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceEstimateFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @data('owner', 'staff', 'manager', 'administrator')
    def test_user_cannot_create_price_estimate_for_project(self, user):
        self.valid_data['scope'] = structure_factories.ProjectFactory.get_url(self.project)

        self.client.force_authenticate(self.users[user])
        response = self.client.post(factories.PriceEstimateFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manually_inputed_price_estimate_replaces_autocalcuted(self):
        price_estimate = factories.PriceEstimateFactory(
            scope=self.service_project_link, month=self.valid_data['month'], year=self.valid_data['year'])

        self.client.force_authenticate(self.users['owner'])
        response = self.client.post(factories.PriceEstimateFactory.get_list_url(), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reread_price_estimate = models.PriceEstimate.objects.get(id=price_estimate.id)
        self.assertFalse(reread_price_estimate.is_visible)


class PriceEstimateUpdateTest(BaseCostTrackingTest):

    def setUp(self):
        super(PriceEstimateUpdateTest, self).setUp()

        self.price_estimate = factories.PriceEstimateFactory(scope=self.service_project_link)
        self.valid_data = {
            'scope': structure_factories.TestServiceProjectLinkFactory.get_url(self.service_project_link),
            'total': 100,
            'details': {'ram': 50, 'disk': 50},
            'month': 7,
            'year': 2015,
        }

    def test_price_estimate_scope_cannot_be_updated(self):
        other_service_project_link = structure_factories.TestServiceProjectLinkFactory(project=self.project)
        self.valid_data['scope'] = structure_factories.TestServiceProjectLinkFactory.get_url(
            other_service_project_link)

        self.client.force_authenticate(self.users['staff'])
        response = self.client.patch(factories.PriceEstimateFactory.get_url(self.price_estimate), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        reread_price_estimate = models.PriceEstimate.objects.get(id=self.price_estimate.id)
        self.assertNotEqual(reread_price_estimate.scope, other_service_project_link)

    def test_autocalculated_estimate_cannot_be_manually_updated(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.patch(factories.PriceEstimateFactory.get_url(self.price_estimate), data=self.valid_data)

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        reread_price_estimate = models.PriceEstimate.objects.get(id=self.price_estimate.id)
        self.assertFalse(reread_price_estimate.is_manually_input)


class PriceEstimateDeleteTest(BaseCostTrackingTest):

    def setUp(self):
        super(PriceEstimateDeleteTest, self).setUp()

        self.manual_link_price_estimate = factories.PriceEstimateFactory(
            scope=self.service_project_link, is_manually_input=True)
        self.auto_link_price_estimate = factories.PriceEstimateFactory(
            scope=self.service_project_link, is_manually_input=False,
            month=self.manual_link_price_estimate.month, year=self.manual_link_price_estimate.year)
        self.project_price_estimate = factories.PriceEstimateFactory(scope=self.project)

    def test_autocreated_price_estimate_cannot_be_deleted(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.delete(factories.PriceEstimateFactory.get_url(self.project_price_estimate))

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_autocreated_price_estimate_become_visible_on_manual_estimate_deletion(self):
        self.client.force_authenticate(self.users['staff'])
        response = self.client.delete(factories.PriceEstimateFactory.get_url(self.manual_link_price_estimate))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        reread_auto_link_price_estimate = models.PriceEstimate.objects.get(id=self.auto_link_price_estimate.id)
        self.assertTrue(reread_auto_link_price_estimate.is_visible)


class ScopeTypeFilterTest(BaseCostTrackingTest):
    def setUp(self):
        super(ScopeTypeFilterTest, self).setUp()
        resource = structure_factories.TestInstanceFactory(service_project_link=self.service_project_link)
        self.estimates = {
            'customer': factories.PriceEstimateFactory(scope=self.customer),
            'service': factories.PriceEstimateFactory(scope=self.service),
            'project': factories.PriceEstimateFactory(scope=self.project),
            'service_project_link': factories.PriceEstimateFactory(scope=self.service_project_link),
            'resource': factories.PriceEstimateFactory(scope=resource),
        }

    def test_user_can_filter_price_estimate_by_scope_type(self):
        self.client.force_authenticate(self.users['owner'])
        for scope_type, estimate in self.estimates.items():
            response = self.client.get(
                factories.PriceEstimateFactory.get_list_url(),
                data={'scope_type': scope_type})

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]['uuid'], estimate.uuid.hex)


@ddt
class HistoricResourceTest(BaseCostTrackingTest):
    def setUp(self):
        super(HistoricResourceTest, self).setUp()
        resource1 = structure_factories.TestInstanceFactory(service_project_link=self.service_project_link)
        self.resource1_estimate = factories.PriceEstimateFactory(scope=resource1)
        resource1.delete()

        resource2 = structure_factories.TestInstanceFactory(service_project_link=self.service_project_link)
        self.resource2_estimate = factories.PriceEstimateFactory(scope=resource2)

    @data('owner', 'staff')
    def test_user_can_filter_price_estimates_by_customer(self, user):
        self.client.force_authenticate(self.users[user])
        response = self.client.get(factories.PriceEstimateFactory.get_list_url(),
                                   {'customer': self.customer.uuid.hex})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_user_can_not_see_historic_resources_for_other_customer(self):
        self.client.force_authenticate(structure_factories.UserFactory())
        response = self.client.get(factories.PriceEstimateFactory.get_list_url(),
                                   {'customer': self.customer.uuid.hex})
        self.assertEqual(len(response.data), 0)

    def test_resource_exposes_scope_type_and_resource_type(self):
        self.client.force_authenticate(self.users['owner'])
        for estimate in (self.resource1_estimate, self.resource2_estimate):
            response = self.client.get(factories.PriceEstimateFactory.get_url(estimate))
            self.assertEqual(response.data['scope_name'], estimate.scope.name)
            self.assertEqual(response.data['scope_type'], 'resource')
            self.assertEqual(response.data['resource_type'], 'Test.TestInstance')


class DeletePriceEstimateForStructureModelsTest(BaseCostTrackingTest):
    def test_if_service_deleted_its_price_estimate_remains(self):
        estimate = factories.PriceEstimateFactory(scope=self.service)
        self.service.delete()
        estimate.refresh_from_db()
        self.assertEqual(estimate.details['scope_name'], self.service.name)
        self.assertEqual(estimate.object_id, None)

    def test_if_settings_deleted_its_price_estimate_remains(self):
        service_settings = self.service.settings
        estimate = factories.PriceEstimateFactory(scope=service_settings)
        service_settings.delete()
        estimate.refresh_from_db()
        self.assertEqual(estimate.details['scope_name'], service_settings.name)
        self.assertEqual(estimate.object_id, None)

    def test_if_project_deleted_its_price_estimate_remains(self):
        estimate = factories.PriceEstimateFactory(scope=self.project)
        self.project.delete()
        estimate.refresh_from_db()
        self.assertEqual(estimate.details['scope_name'], self.project.name)
        self.assertEqual(estimate.object_id, None)

    def test_if_customer_deleted_its_price_estimate_deleted(self):
        estimate = factories.PriceEstimateFactory(scope=self.customer)
        self.customer.projects.all().delete()
        self.customer.project_groups.all().delete()
        self.customer.delete()
        self.assertFalse(models.PriceEstimate.objects.filter(id=estimate.id).exists())
