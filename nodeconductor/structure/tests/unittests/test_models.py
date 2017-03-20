from django.test import TestCase

from nodeconductor.structure.tests import factories


class ServiceProjectLinkTest(TestCase):

    def setUp(self):
        self.link = factories.TestServiceProjectLinkFactory()

    def test_link_is_in_certification_erred_state_if_service_does_not_satisfy_project_certifications(self):
        certification = factories.ServiceCertificationFactory()
        self.assertEqual(self.link.CertificationState.OK, self.link.policy_compliant)

        self.link.project.certifications.add(certification)

        self.assertEqual(self.link.CertificationState.ERRED, self.link.policy_compliant)

    def test_link_is_in_certification_ok_state_if_project_certifications_is_a_subset_of_service_certifications(self):
        certifications = factories.ServiceCertificationFactory.create_batch(2)
        self.link.project.certifications.add(*certifications)
        certifications.append(factories.ServiceCertificationFactory())

        self.link.service.settings.certifications.add(*certifications)

        self.assertEqual(self.link.CertificationState.OK, self.link.policy_compliant)

