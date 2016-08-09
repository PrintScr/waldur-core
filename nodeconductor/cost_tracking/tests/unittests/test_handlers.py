from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from nodeconductor.cost_tracking import CostTrackingRegister, models
from nodeconductor.cost_tracking.tests import factories
from nodeconductor.structure.tests import factories as structure_factories
from nodeconductor.structure.tests.models import TestNewInstance


class UpdateConsumptionDetailsOnResourceUpdateTest(TestCase):

    def setUp(self):
        CostTrackingRegister.register_strategy(factories.TestNewInstanceCostTrackingStrategy)

    @freeze_time('2016-08-08 11:00:00', tick=True)  # freeze time to avoid bugs between in the end of the month.
    def test_consumtion_details_of_resource_is_keeped_up_to_date(self):
        today = timezone.now()
        configuration = dict(ram=2048, disk=20 * 1024, cores=2)
        resource = structure_factories.TestNewInstanceFactory(
            state=TestNewInstance.States.OK, runtime_state='online', **configuration)

        price_estimate = models.PriceEstimate.objects.get(scope=resource, month=today.month, year=today.year)
        consumption_details = price_estimate.consumption_details
        self.assertDictEqual(consumption_details.configuration, configuration)

        resource.ram = 1024
        resource.save()

        consumption_details.refresh_from_db()
        self.assertEqual(consumption_details.configuration['ram'], resource.ram)

        resource.runtime_state = 'offline'
        resource.save()

        expected = dict(ram=0, disk=20 * 1024, cores=0)
        consumption_details.refresh_from_db()
        self.assertDictEqual(consumption_details.configuration, expected)
