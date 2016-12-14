from datetime import timedelta

from ddt import ddt, data
from django.utils import timezone
from rest_framework import test, status

from nodeconductor.structure import models as structure_models
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.users import models, tasks
from nodeconductor.users.tests import factories


@ddt
class InvitationPermissionApiTest(test.APITransactionTestCase):
    def setUp(self):
        self.staff = structure_factories.UserFactory(is_staff=True)
        self.customer_owner = structure_factories.UserFactory()
        self.project_admin = structure_factories.UserFactory()
        self.project_manager = structure_factories.UserFactory()
        self.user = structure_factories.UserFactory()

        self.customer = structure_factories.CustomerFactory()
        self.customer.add_user(self.customer_owner, structure_models.CustomerRole.OWNER)

        self.customer_role = self.customer.roles.get(role_type=structure_models.CustomerRole.OWNER)
        self.customer_invitation = factories.CustomerInvitationFactory(customer_role=self.customer_role)

        self.project = structure_factories.ProjectFactory(customer=self.customer)
        self.project.add_user(self.project_admin, structure_models.ProjectRole.ADMINISTRATOR)
        self.project.add_user(self.project_manager, structure_models.ProjectRole.MANAGER)

        self.project_role = self.project.roles.get(role_type=structure_models.ProjectRole.ADMINISTRATOR)
        self.project_invitation = factories.ProjectInvitationFactory(project_role=self.project_role)

    # List tests
    def test_user_can_list_invitations(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(factories.InvitationBaseFactory.get_list_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Retrieve tests
    @data('staff', 'customer_owner')
    def test_user_with_access_can_retrieve_project_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.get(factories.ProjectInvitationFactory.get_url(self.project_invitation))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @data('project_admin', 'project_manager', 'user')
    def test_user_without_access_cannot_retrieve_project_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.get(factories.ProjectInvitationFactory.get_url(self.project_invitation))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @data('staff', 'customer_owner')
    def test_user_with_access_can_retrieve_customer_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.get(factories.CustomerInvitationFactory.get_url(self.customer_invitation))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @data('project_admin', 'project_manager', 'user')
    def test_user_without_access_cannot_retrieve_customer_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.get(factories.CustomerInvitationFactory.get_url(self.customer_invitation))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # Creation tests
    @data('staff', 'customer_owner')
    def test_user_with_access_can_create_project_admin_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        payload = self._get_valid_project_invitation_payload(self.project_invitation, project_role='admin')
        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @data('staff', 'customer_owner')
    def test_user_with_access_can_create_project_manager_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        payload = self._get_valid_project_invitation_payload(self.project_invitation, project_role='manager')
        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @data('project_admin', 'project_manager', 'user')
    def test_user_without_access_cannot_create_project_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        payload = self._get_valid_project_invitation_payload(self.project_invitation)
        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, {'detail': 'You do not have permission to perform this action.'})

    @data('staff', 'customer_owner')
    def test_user_with_access_can_create_customer_owner_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        payload = self._get_valid_customer_invitation_payload(self.customer_invitation)
        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @data('project_admin', 'project_manager', 'user')
    def test_user_without_access_cannot_create_customer_owner_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        payload = self._get_valid_customer_invitation_payload(self.customer_invitation)
        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data, {'detail': 'You do not have permission to perform this action.'})

    @data('staff', 'customer_owner')
    def test_user_with_access_can_cancel_project_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.post(factories.ProjectInvitationFactory.get_url(self.project_invitation,
                                                                               action='cancel'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project_invitation.refresh_from_db()
        self.assertEqual(self.project_invitation.state, models.Invitation.State.CANCELED)

    @data('project_admin', 'project_manager', 'user')
    def test_user_without_access_cannot_cancel_project_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.post(factories.ProjectInvitationFactory.get_url(self.project_invitation,
                                                                               action='cancel'))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @data('staff', 'customer_owner')
    def test_user_with_access_can_cancel_customer_invitation(self, user):
        self.client.force_authenticate(user=getattr(self, user))
        response = self.client.post(factories.CustomerInvitationFactory.get_url(self.customer_invitation,
                                                                                action='cancel'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer_invitation.refresh_from_db()
        self.assertEqual(self.customer_invitation.state, models.Invitation.State.CANCELED)

    def test_authenticated_user_can_accept_project_invitation(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(factories.ProjectInvitationFactory.get_url(
            self.project_invitation, action='accept'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.project_invitation.refresh_from_db()
        self.assertEqual(self.project_invitation.state, models.Invitation.State.ACCEPTED)
        self.assertTrue(self.project.has_user(self.user, self.project_invitation.project_role.role_type))

    def test_authenticated_user_can_accept_customer_invitation(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(factories.CustomerInvitationFactory.get_url(
            self.customer_invitation, action='accept'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.customer_invitation.refresh_from_db()
        self.assertEqual(self.customer_invitation.state, models.Invitation.State.ACCEPTED)
        self.assertTrue(self.customer.has_user(self.user, self.customer_invitation.customer_role.role_type))

    def test_user_with_invalid_civil_number_cannot_accept_invitation(self):
        customer_invitation = factories.CustomerInvitationFactory(customer_role=self.customer_role,
                                                                  civil_number='123456789')
        self.client.force_authenticate(user=self.user)
        response = self.client.post(factories.CustomerInvitationFactory.get_url(customer_invitation, action='accept'))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, ['User has an invalid civil number.'])

    def test_user_which_already_has_role_within_customer_cannot_accept_invitation(self):
        customer_invitation = factories.CustomerInvitationFactory(customer_role=self.customer_role)
        self.client.force_authenticate(user=self.user)
        self.customer.add_user(self.user, customer_invitation.customer_role.role_type)
        response = self.client.post(factories.CustomerInvitationFactory.get_url(customer_invitation, action='accept'))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, ['User already has role within this customer.'])

    def test_user_which_already_has_role_within_project_cannot_accept_invitation(self):
        project_invitation = factories.ProjectInvitationFactory(project_role=self.project_role)
        self.client.force_authenticate(user=self.user)
        self.project.add_user(self.user, project_invitation.project_role.role_type)
        response = self.client.post(factories.ProjectInvitationFactory.get_url(project_invitation, action='accept'))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, ['User already has role within this project.'])

    # API tests
    def test_user_cannot_create_invitation_with_invalid_link_template(self):
        self.client.force_authenticate(user=self.staff)
        payload = self._get_valid_project_invitation_payload(self.project_invitation)
        payload['link_template'] = '/invalid/link'
        response = self.client.post(factories.ProjectInvitationFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'link_template': ["Link template must include '{uuid}' parameter."]})

    def test_user_cannot_create_invitation_for_project_and_customer_simultaneously(self):
        self.client.force_authenticate(user=self.staff)
        payload = self._get_valid_project_invitation_payload(self.project_invitation)
        customer_payload = self._get_valid_customer_invitation_payload(self.customer_invitation)
        payload['customer'] = customer_payload['customer']
        payload['customer_role'] = customer_payload['customer_role']

        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data,
                         {'non_field_errors': ["Cannot create invitation to project and customer simultaneously."]})

    def test_user_cannot_create_invitation_without_customer_or_project(self):
        self.client.force_authenticate(user=self.staff)
        payload = self._get_valid_project_invitation_payload(self.project_invitation)
        payload.pop('project')

        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'non_field_errors': ["Customer or project must be provided."]})

    def test_user_cannot_create_project_invitation_without_project_role(self):
        self.client.force_authenticate(user=self.staff)
        payload = self._get_valid_project_invitation_payload(self.project_invitation)
        payload.pop('project_role')

        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'project_role': ["Project and its role must be provided."]})

    def test_user_cannot_create_customer_invitation_without_customer_role(self):
        self.client.force_authenticate(user=self.staff)
        payload = self._get_valid_customer_invitation_payload(self.customer_invitation)
        payload.pop('customer_role')

        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, {'customer_role': ["Customer and its role must be provided."]})

    def test_user_can_create_invitation_for_existing_user(self):
        self.client.force_authenticate(user=self.staff)
        email = 'test@example.com'
        structure_factories.UserFactory(email=email)
        payload = self._get_valid_project_invitation_payload(self.project_invitation)
        payload['email'] = email

        response = self.client.post(factories.InvitationBaseFactory.get_list_url(), data=payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invitation_is_canceled_after_expiration_date(self):
        with self.settings(NODECONDUCTOR={'INVITATION_LIFETIME': timedelta(weeks=1)}):
            invitation = factories.ProjectInvitationFactory(created=timezone.now() - timedelta(weeks=1))
            tasks.cancel_expired_invitations()

        self.assertEqual(models.Invitation.objects.get(uuid=invitation.uuid).state, models.Invitation.State.EXPIRED)

    def test_filtering_by_customer_uuid_includes_project_invitations_for_that_customer_too(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(factories.InvitationBaseFactory.get_list_url(), {
            'customer': self.customer.uuid.hex
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_filtering_by_customer_url_includes_project_invitations_for_that_customer_too(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(factories.InvitationBaseFactory.get_list_url(), {
            'customer_url': structure_factories.CustomerFactory.get_url(self.customer)
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_filtering_by_another_customer_does_not_includes_project_invitations_for_initial_customer(self):
        other_customer = structure_factories.CustomerFactory()
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(factories.InvitationBaseFactory.get_list_url(), {
            'customer': other_customer.uuid.hex
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    # Helper methods
    def _get_valid_project_invitation_payload(self, invitation=None, project_role=None):
        invitation = invitation or factories.ProjectInvitationFactory.build()
        return {
            'email': invitation.email,
            'link_template': invitation.link_template,
            'project': structure_factories.ProjectFactory.get_url(invitation.project_role.project),
            'project_role': project_role or 'admin',
        }

    def _get_valid_customer_invitation_payload(self, invitation=None, customer_role=None):
        invitation = invitation or factories.CustomerInvitationFactory.build()
        return {
            'email': invitation.email,
            'link_template': invitation.link_template,
            'customer': structure_factories.CustomerFactory.get_url(invitation.customer),
            'customer_role': customer_role or 'owner',
        }
