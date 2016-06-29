import re

from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.db.models import OneToOneField, ForeignKey
from django.db.models.query import QuerySet

from edc_base.form.classes import LogicCheck
from edc_constants.constants import YES, NO, OTHER, NOT_APPLICABLE


class BaseModelForm(forms.ModelForm):

    visit_model = None
    optional_attrs = {}

    def __init__(self, *args, **kwargs):
        super(BaseModelForm, self).__init__(*args, **kwargs)
        self.logic = LogicCheck(self._meta.model)

    def get_subject_identifier(self, cleaned_data):
        subject_identifier = None
        if 'subject_identifier' in cleaned_data:
            subject_identifier = cleaned_data.get('subject_identifier')
        if not subject_identifier:
            if 'registered_subject' in cleaned_data:
                subject_identifier = cleaned_data.get('registered_subject').subject_identifier
        if not subject_identifier:
            if not self.visit_model:
                raise ImproperlyConfigured('Expected a value for class attr visit_model. Got None.')
            for field in self._meta.model._meta.fields:
                if isinstance(field, (OneToOneField, ForeignKey)):
                    if isinstance(field.rel.to, self.visit_model):
                        attrname = field.attrname
                        visit = cleaned_data.get(attrname, None)
                        if visit:
                            subject_identifier = visit.get_subject_identifier()
        return subject_identifier

    def clean(self):
        """Calls crypto clean methods, OTHER/Specify and some functionality for bhp_dispatch."""
        cleaned_data = super(BaseModelForm, self).clean()
        self.encrypted_fields_validation()
        self.other_fields()
        self.check_for_other_in_m2m()
        return cleaned_data

    def other_fields(self):
        cleaned_data = self.cleaned_data
        # check for OTHER in choices tuples, if selected, should have a value on Other specify.
        other = []
        for fld in cleaned_data.keys():
            if cleaned_data.get(fld, None) in ['other', 'Other', OTHER]:
                other.append(fld)
        for fld in other:
            if '{0}_other'.format(fld) in cleaned_data:
                if not cleaned_data.get('{0}_other'.format(fld)):
                    raise forms.ValidationError(
                        'If {0} is \'OTHER\', please specify. '
                        'You wrote \'{1}\''.format(fld, cleaned_data['{0}_other'.format(fld)]))

    def encrypted_fields_validation(self):
        """Encrypted fields may have their own validation code to run.

        See the custom field objects in edc.core.crypto_fields."""
        # TODO: is this used??
        cleaned_data = self.cleaned_data
        try:
            from edc.core.crypto_fields.fields import BaseEncryptedField
            for field in self._meta.model._meta.fields:
                if isinstance(field, BaseEncryptedField):
                    field.validate_with_cleaned_data(field.attname, cleaned_data)
        except ImportError:
            pass

    def check_for_other_in_m2m(self):
        """Raises ValidtionError for an m2m if it cannot confirm \'Other Specify\'
        is paired with a value in a following \'other\' field."""
        cleaned_data = self.cleaned_data
        for field_name, field_value in cleaned_data.items():
            self.check_for_value_in_m2m(
                cleaned_data, field_name, field_value,
                '{0}_other'.format(field_name),
                ['specify', 'explain'],
                'other')

    def check_for_value_in_m2m(self, cleaned_data, m2m_name, m2m_qs, optional_field_name,
                               optional_words, required_word=None):
        """Raises ValidtionError for an m2m if it cannot confirm \'Other Specify\'
        is paired with a value in a following \'other\' field."""
        if not required_word:
            required_word = ''
        if isinstance(m2m_qs, QuerySet):
            try:
                answers = [l.name.lower() for l in cleaned_data.get(m2m_name, [])]
            except AttributeError:
                answers = [l.short_name.lower() for l in cleaned_data.get(m2m_name, [])]
            if answers:
                for ans in answers:
                    if any([word in ans for word in optional_words]) and required_word in ans.lower():
                        if not cleaned_data.get(optional_field_name, None):
                            raise forms.ValidationError(
                                'You have selected \'{0}\' as an answer for {1}. '
                                'Please specify in {2}.'.format(ans, m2m_name, optional_field_name))

    # TODO: is this method used??
    def validate_m2m(self, **kwargs):
        """Validates at form level a triplet of questions lead by a Yes/No for a
        many to many with other specify.

            * The first question is a Yes/No question indicating if any items
              in the many to many will be selected
            * The second question is a many to many (select all that apply)
            * The third is an 'Other Specify' to be completed if an 'Other'
              item was selected in the many to many question

            Be sure to check cleaned_data for the 'key' of the m2m field first.

            For example, in the ModelForm clean() method call::

                if cleaned_data.has_key('chronic_cond'):
                    self.validate_m2m(
                            label = 'chronic condition',
                            yesno = cleaned_data['chronic_cond_since'],
                            m2m = cleaned_data['chronic_cond'],
                            other = cleaned_data['chronic_cond_other'])
        """
        label = kwargs.get('label', 'items to be selected')
        leading = kwargs.get('leading')
        m2m = kwargs.get('m2m') or []
        other = kwargs.get('other')

        # if leading question is 'Yes', a m2m item cannot be 'Not applicable'
        if leading == YES and [True for item in m2m if item.name == NOT_APPLICABLE]:
            raise forms.ValidationError(
                "You stated there ARE " + label + "s, yet you selected '{0}'".format(item.name))

        # if leading question is 'No', ensure the m2m item is 'not applicable'
        if leading == NO and not [True for item in m2m if item.name == NOT_APPLICABLE]:
            raise forms.ValidationError("You stated there are NO {0}s. Please correct".format(label))

        # if leading question is 'No', ensure only one m2m item is selected.
        if leading == NO and len(m2m) > 1:
            raise forms.ValidationError("You stated there are NO {0}s. Please correct".format(label))

        # if leading question is 'Yes' and an m2m item is 'other, specify', ensure 'other' attribute has a value
        if leading == YES and not other and [True for item in m2m if 'other' in item.name.lower()]:
            raise forms.ValidationError("You have selected a '{0}' as 'Other', please specify.".format(label))

        # if 'other' has a value but no m2m item is 'Other, specify'
        if other and not [True for item in m2m if 'other' in item.name.lower()]:
            raise forms.ValidationError(
                'You have specified an \'Other\' {0} but not selected \'Other, specify\'. '
                'Please correct.'.format(label))

    def validate_m2m_wcs_dx(self, **kwargs):
        label = kwargs.get('label', 'items to be selected')
        leading = kwargs.get('leading')
        m2m = kwargs.get('m2m')
        other = kwargs.get('other')

        # if leading question is 'Yes', a m2m item cannot be 'Not applicable'
        if (leading == YES and [
                True for item in m2m if (item.short_name == NOT_APPLICABLE or
                                         item.short_name.lower() == 'asymptomatic')]):
            raise forms.ValidationError(
                "You stated there ARE " + label + "s, yet you selected '{0}'".format(item.short_name))

        # if leading question is 'No', ensure the m2m item is 'not applicable'
        if (leading == NO and not [
                True for item in m2m if (item.short_name == NOT_APPLICABLE or
                                         item.short_name.lower() == 'asymptomatic')]):
            raise forms.ValidationError("You stated there are NO {0}s. Please correct".format(label))

        # if leading question is 'No', ensure only one m2m item is selected.
        if leading == NO and len(m2m) > 1:
            raise forms.ValidationError("You stated there are NO {0}s. Please correct".format(label))

        # if leading question is 'Yes' and an m2m item is 'other, specify', ensure 'other' attribute has a value
        if leading == YES and not other and [True for item in m2m if 'other' in item.short_name.lower()]:
            raise forms.ValidationError("You have selected a '{0}' as 'Other', please specify.".format(label))

        # if 'other' has a value but no m2m item is 'Other, specify'
        if other and not [True for item in m2m if 'other' in item.short_name.lower()]:
            raise forms.ValidationError(
                'You have specified an \'Other\' {0} but not selected \'Other, specify\'. '
                'Please correct.'.format(label))

    def options_in_tuple(self, choices, options):
        """Confirms options exist in choices tuple."""
        if not isinstance(choices, tuple):
            raise TypeError('Parameter \'choices\' must be a tuple.')
        if not isinstance(options, list):
            raise TypeError('Parameter \'options\' must be a list.')
        choices = list(choices)
        choices.sort()
        lst = list(set(list(options) + choices))
        lst.sort()
        if not lst == choices:
            raise TypeError(
                'Options {0} are not in choices tuple {1}. Has the choices tuple changed?'.format(
                    options, choices))

    def verify_tuples(self):
        """Override to verify tuple values referenced in the valifation checks.

        For example, validation checks refer to values from these choices::
            options = ['Yes', 'No', 'not sure', 'Don\'t want to answer']
            self.options_in_tuple(YES_NO_UNSURE, options)
            self.options_in_tuple(FIRSTPARTNERHIV_CHOICE, ['negative', 'I am not sure'])
        """
        pass

    def _validate_cleaned_data(self, cleaned_data, supress_exception=None):

        self.validate_cleaned_data(cleaned_data)
        if self.get_validation_error() and not supress_exception:
            for message in self.get_validation_error().values():
                raise forms.ValidationError(message)
        return self.get_validation_error()

    def validate_cleaned_data(self, cleaned_data, suppress_exception=None):
        """Override to add validation code in a manner that is easier to test.

        Instead of adding validation code to the clean() method, add it
        to this method. Then in your tests do something like this::
            ...
            print 'test maternal visit'
            form = MaternalVisitForm()
            self.assertEquals(form._validate_cleaned_data({}), None)
            self.assertRaises(
                ValidationError, form._validate_cleaned_data,
                {'reason': 'missed', 'reason_missed': None})
            self.assertIsNotNone(
                form._validate_cleaned_data({
                    'reason': 'missed', 'reason_missed': None}, supress_exception=True).get(1, None))
            ...

        .. note:: in your test call :fun:`_validate_cleaned_data` instead of :fun:`validate_cleaned_data`

        Since :func:`clean` is called in super, there is no need to override it nor for this method
        to return cleaned_data. So instead of this, in the clean method::

            if cleaned_data.get('reason') == 'missed' and not cleaned_data.get('reason_missed'):
                raise forms.ValidationError('Please provide the reason the scheduled visit was missed')

        ... do this in :func:`validate_cleaned_data`::

            if cleaned_data.get('reason') == 'missed' and not cleaned_data.get('reason_missed'):
                self.set_validation_error({1: 'an error has occurred'})

        ... then in the test, inspect the return value::

            self.assertIsNotNone(
                form._validate_cleaned_data({
                    'reason': 'missed', 'reason_missed': None}, supress_exception=True).get(1, None))

        """
        pass

    @property
    def number_from_label(self):
        """Returns the question number from the label, or None."""
        try:
            number = re.match('^\\d+\\.', self.fields['week32_test_date'].label).string.split('.')
        except AttributeError:
            number = ['']
        return number[0]