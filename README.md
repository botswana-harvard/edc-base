[![Build Status](https://travis-ci.org/clinicedc/edc-base.svg?branch=develop)](https://travis-ci.org/clinicedc/edc-base)
[![Coverage Status](https://coveralls.io/repos/clinicedc/edc-base/badge.svg?branch=develop&service=github)](https://coveralls.io/github/clinicedc/edc-base?branch=develop)
# edc-base

Base model, manager, field, form and admin classes for Edc. 


Installation
------------

In the __settings__ file add:

	STUDY_OPEN_DATETIME = datetime.today()
	STUDY_CLOSE_DATETIME = datetime.today()
	GENDER_OF_CONSENT = ['M', 'F']

Optional __settings__ attributes:

	# phone number validtors
	# the default is '^[0-9+\(\)#\.\s\/ext-]+$'
	TELEPHONE_REGEX = '^[2-8]{1}[0-9]{6}$'
	CELLPHONE_REGEX = '^[7]{1}[12345678]{1}[0-9]{6}$',

### ModelForm Mixin

#### CommonCleanModelFormMixin

Works together with `common_clean` on the model that inherits from `BaseModel`.

The validation logic lives on the model but can be called in time for the ModelForm.clean() to re-raise the exceptions and place the error messages on the ModelForm page.

If the exception instance has a second `arg` it will be used as the form field name and the error message will be placed by the field on the page.

For example:

On the model you must use `BaseModel`:

    from edc_base.model.models import BaseModel


    class MyModel(BaseModel, models.Model):
    
        f1 = models.CharField(...)

        f2 = models.CharField(...)

        def common_clean(self):
            # note: (1) this code should be validation code. Avoid setting any field attributes here.
            #       (2) this method will be called in the model save method as well.
            if f1 != 'happiness': 
                raise ExceptionOne('Expected happiness.', 'f1')
            if f2 != 'liberty': 
                raise ExceptionTwo('Expected liberty.', 'f2')
            super().common_clean()

        @property
        def common_clean_exceptions(self):
            common_clean_exceptions = super().common_clean_exceptions
            common_clean_exceptions.extend([ExceptionOne, ExceptionTwo])
            return common_clean_exceptions
    
On the ModelForm, just add the mixin. If you do override `clean()` be sure to call `super()`.

    from edc_base.form_mixins import CommonCleanModelFormMixin


    MyModelForm(CommonCleanModelFormMixin, for.ModelForm):

        def clean(self):
            cleaned_data = super().clean()
            ...
            ...
            ...
            return cleaned_data



### Model Field Validators

__CompareNumbersValidator:__ Compare the field value to a static value. For example, validate that the
age of consent is between 18 and 64. 

    consent_age = models.IntegerField(
        validators=[
            CompareNumbersValidator(18, '>=', message='Age of consent must be {}. Got {}'),
            CompareNumbersValidator(64, '<=', message='Age of consent must be {}. Got {}')
        ]

Or you can use the special validators `MinConsentAgeValidator`, `MaxConsentAgeValidator`:

    consent_age = models.IntegerField(
        validators=[
            MinConsentAgeValidator(18),
            MaxConsentAgeValidator(64)
        ]

### Test server vs live server:

The theme of the test server and the live server are controlled by site name.
For a test server site name should always be `Example.com` whereas the live server it should be anything else.


### Audit trail (HistoricalRecord):

(in development PY3/DJ1.8+)

HistoricalRecord is an almost identical version of `simple_history.models.HistoricalRecord`
with the exception of two methods:  `get_extra_fields()` and `add_extra_methods()`. Method 
`get_extra_fields()` method is overridden to change the *history_id* primary key from an 
`IntegerField` to a `UUIDField` so that it can work with module `edc-sync`. Method `add_extra_methods()`
is overridden to add the methods from `edc_sync.mixins.SyncMixin` if module `edc_sync` is 
in INSTALLED_APP.


    from edc_base.model.models import HistoricalRecord
    from edc_sync.mixins import SyncMixin
    
    class MyModel(SyncMixin, BaseUuidModel):
        
        ...
        history = HistoricalRecord()
        
        class Meta:
            app_label = 'my_app'    

The audit trail models created by `simple_history` have a foreign key to `auth.User`.
In order for the models to work with `edc_sync` specify the edc_sync User model in settings:
    
    AUTH_USER_MODEL = 'edc_sync.User' 


### Notes

User created and modified fields behave as follows:
* created is only set on pre-save add
* modified is always updated
