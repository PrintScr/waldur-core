from ddt import ddt, data

from rest_framework import status, test

from nodeconductor.structure import models

from . import fixtures, factories


class ServiceSettingsListTest(test.APITransactionTestCase):
    def setUp(self):
        self.users = {
            'staff': factories.UserFactory(is_staff=True),
            'owner': factories.UserFactory(),
            'not_owner': factories.UserFactory(),
        }

        self.customers = {
            'owned': factories.CustomerFactory(),
            'inaccessible': factories.CustomerFactory(),
        }

        self.customers['owned'].add_user(self.users['owner'], models.CustomerRole.OWNER)

        self.settings = {
            'shared': factories.ServiceSettingsFactory(shared=True),
            'inaccessible': factories.ServiceSettingsFactory(customer=self.customers['inaccessible']),
            'owned': factories.ServiceSettingsFactory(
                customer=self.customers['owned'], backend_url='bk.url', password='123'),
        }

        # Token is excluded, because it is not available for OpenStack
        self.credentials = ('backend_url', 'username', 'password')

    def test_user_can_see_shared_settings(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.get(factories.ServiceSettingsFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 1)
        self.assert_credentials_hidden(response.data[0])
        self.assertEqual(response.data[0]['uuid'], self.settings['shared'].uuid.hex, response.data)

    def test_user_can_see_shared_and_own_settings(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.get(factories.ServiceSettingsFactory.get_list_url())
        uuids_recieved = [d['uuid'] for d in response.data]
        uuids_expected = [self.settings[s].uuid.hex for s in ('shared', 'owned')]
        self.assertItemsEqual(uuids_recieved, uuids_expected, response.data)

    def test_admin_can_see_all_settings(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(factories.ServiceSettingsFactory.get_list_url())
        uuids_recieved = [d['uuid'] for d in response.data]
        uuids_expected = [s.uuid.hex for s in self.settings.values()]
        self.assertItemsEqual(uuids_recieved, uuids_expected, uuids_recieved)

    def test_user_can_see_credentials_of_own_settings(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.get(factories.ServiceSettingsFactory.get_url(self.settings['owned']))
        self.assert_credentials_visible(response.data)

    def test_user_cant_see_others_settings(self):
        self.client.force_authenticate(user=self.users['not_owner'])

        response = self.client.get(factories.ServiceSettingsFactory.get_url(self.settings['owned']))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_can_see_all_credentials(self):
        self.client.force_authenticate(user=self.users['staff'])

        response = self.client.get(factories.ServiceSettingsFactory.get_url(self.settings['owned']))
        self.assert_credentials_visible(response.data)

    def test_user_cant_see_shared_credentials(self):
        self.client.force_authenticate(user=self.users['owner'])

        response = self.client.get(factories.ServiceSettingsFactory.get_url(self.settings['shared']))
        self.assert_credentials_hidden(response.data)

    def assert_credentials_visible(self, data):
        for field in self.credentials:
            self.assertIn(field, data)

    def assert_credentials_hidden(self, data):
        for field in self.credentials:
            self.assertNotIn(field, data)


@ddt
class ServiceSettingUpdateTest(test.APITransactionTestCase):

    def setUp(self):
        self.fixture = fixtures.ServiceFixture()
        self.service_settings = self.fixture.service_settings
        self.service_settings.shared = True
        self.service_settings.save()
        self.url = factories.ServiceSettingsFactory.get_url(self.service_settings)

    def get_valid_payload(self):
        return {'name': 'test'}

    @data('staff')
    def test_user_can_update_service_settings_without_customer_if_he_has_permission(self, user):
        self.service_settings.customer = None
        self.service_settings.save()
        self.client.force_authenticate(getattr(self.fixture, user))
        payload = self.get_valid_payload()

        response = self.client.patch(self.url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service_settings.refresh_from_db()
        self.assertEqual(self.service_settings.name, payload['name'])

    @data('owner', 'manager', 'admin')
    def test_user_cannot_update_service_settings_without_customer_if_he_has_no_permission(self, user):
        self.service_settings.customer = None
        self.service_settings.save()
        self.client.force_authenticate(getattr(self.fixture, user))
        payload = self.get_valid_payload()

        response = self.client.patch(self.url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.service_settings.refresh_from_db()
        self.assertNotEqual(self.service_settings.name, payload['name'])

    @data('staff', 'owner')
    def test_user_can_update_service_settings_with_customer_if_he_has_permission(self, user):
        self.client.force_authenticate(getattr(self.fixture, user))
        payload = self.get_valid_payload()

        response = self.client.patch(self.url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service_settings.refresh_from_db()
        self.assertEqual(self.service_settings.name, payload['name'])

    @data('manager', 'admin')
    def test_user_cannot_update_service_settings_with_customer_if_he_has_no_permission(self, user):
        self.client.force_authenticate(getattr(self.fixture, user))
        payload = self.get_valid_payload()

        response = self.client.patch(self.url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.service_settings.refresh_from_db()
        self.assertNotEqual(self.service_settings.name, payload['name'])

    def test_user_cannot_change_settings_type(self):
        self.client.force_authenticate(user=self.fixture.owner)
        payload = {'name': 'Test backend', 'type': 2}

        response = self.client.patch(self.url, payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service_settings.refresh_from_db()
        self.assertNotEqual(self.service_settings.type, payload['type'], response.data)

    def test_user_can_change_settings_password(self):
        self.client.force_authenticate(user=self.fixture.owner)
        payload = {'password': 'secret'}

        response = self.client.patch(self.url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.service_settings.refresh_from_db()
        self.assertEqual(self.service_settings.password, payload['password'], response.data)


@ddt
class ServiceSettingsUpdateCertifications(test.APITransactionTestCase):

    def setUp(self):
        self.fixture = fixtures.ServiceFixture()
        self.settings = self.fixture.service_settings
        self.settings.shared = True
        self.settings.save()
        self.certification = factories.ServiceCertificationFactory()
        self.url = factories.ServiceSettingsFactory.get_url(self.settings, 'update_certifications')
        self.payload = {'certifications': [factories.ServiceCertificationFactory.get_url(self.certification)]}

    @data('staff', 'owner')
    def test_user_can_update_certifications(self, user):
        self.client.force_authenticate(getattr(self.fixture, user))

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.settings.refresh_from_db()
        self.assertTrue(self.settings.certifications.filter(pk=self.certification.pk).exists())

    @data('manager', 'admin', 'global_support')
    def test_user_can_not_update_certifications_if_he_is_not_staff(self, user):
        self.client.force_authenticate(getattr(self.fixture, user))

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_update_certifications_if_settings_are_shared(self):
        self.client.force_authenticate(self.fixture.owner)
        self.settings.shared = True
        self.settings.save()

        response = self.client.post(self.url, self.payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.settings.refresh_from_db()
        self.assertTrue(self.settings.certifications.filter(pk=self.certification.pk).exists())
