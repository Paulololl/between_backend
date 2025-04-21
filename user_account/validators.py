import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CapitalFirstLetterValidator:
    def validate(self, password, user=None):
        if not password[0].isupper():
            raise ValidationError(
                _('The password must start with a capital letter.'),
                code='capital_first_letter',
            )

    def get_help_text(self):
        return _('The password must start with a capital letter.')


class SpecialCharacterValidator:
    def validate(self, password, user=None):
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError(
                _('The password must contain at least one special character (!@#$%^&* etc).'),
                code='special_character',
            )

    def get_help_text(self):
        return _("Your password must contain at least one special character (!@#$%^&* etc).")


class NumberRequiredValidator:
    def validate(self, password, user=None):
        if not any(char.isdigit() for char in password):
            raise ValidationError(
                _('The password must contain at least one numeric character.'),
                code='number_required',
            )

    def get_help_text(self):
        return _('Your password must contain at least one numeric character.')