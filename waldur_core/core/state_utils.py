from django.utils.encoding import force_text
from waldur_core.core.models import StateMixin


class StateUtils(object):
    @staticmethod
    def to_human_readable_state(state_to_transform):
        return force_text(dict(StateMixin.States.CHOICES)[state_to_transform])
