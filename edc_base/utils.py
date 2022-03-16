import arrow
import random
import re

from dateutil import tz
from dateutil.relativedelta import relativedelta
from decimal import Decimal, InvalidOperation
from math import ceil
from uuid import uuid4

from django.conf import settings
from django.utils.encoding import force_str

from edc_base.exceptions import AgeValueError

safe_allowed_chars = 'ABCDEFGHKMNPRTUVWXYZ2346789'


class MyTimezone:

    def __init__(self, timezone):
        if timezone:
            self.tzinfo = tz.gettz(timezone)
        else:
            self.tzinfo = tz.gettz(settings.TIME_ZONE)


class ConvertError(Exception):
    pass


def get_uuid():
    return uuid4().hex


def round_up(value, digits):
    ceil(value * (10 ** digits)) / (10 ** digits)


def get_safe_random_string(length=12, safe=None, allowed_chars=None):
    safe = True if safe is None else safe
    allowed_chars = (allowed_chars or
                     'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRTUVWXYZ012346789!@#%^&*()?<>.,[]{}')
    if safe:
        allowed_chars = 'ABCDEFGHKMNPRTUVWXYZ2346789'
    return ''.join([random.choice(allowed_chars) for _ in range(length)])


def convert_php_dateformat(php_format_string):
    php_to_python = {
        'A': '%p', 'D': '%a', 'F': '%B', 'H': '%H', 'M': '%b', 'N': '%b',
        'W': '%W', 'Y': '%Y', 'd': '%d', 'e': '%Z', 'h': '%I', 'i': '%M',
        'l': '%A', 'm': '%m', 's': '%S', 'w': '%w', 'y': '%y', 'z': '%j',
        'j': '%d', 'P': '%I:%M %p'}
    python_format_string = php_format_string
    for php, py in php_to_python.items():
        python_format_string = python_format_string.replace(php, py)
    return python_format_string


def get_utcnow():
    return arrow.utcnow().datetime


def to_arrow_utc(dt, timezone=None):
    """Returns a datetime after converting date or datetime from the given timezone string to \'UTC\'."""
    try:
        dt.date()
    except AttributeError:
        # handle born as date. Use 0hr as time before converting to UTC
        tzinfo = MyTimezone(timezone).tzinfo
        r_utc = arrow.Arrow.fromdate(dt, tzinfo=tzinfo).to('utc')
    else:
        # handle born as datetime
        r_utc = arrow.Arrow.fromdatetime(dt, tzinfo=dt.tzinfo).to('utc')
    return r_utc


def age(born, reference_dt, timezone=None):
    """Returns a relative delta"""
    # avoid null dates/datetimes
    if not born:
        raise AgeValueError('Date of birth is required.')
    if not reference_dt:
        raise AgeValueError('Reference date is required.')
    # convert dates or datetimes to UTC datetimes
    born_utc = to_arrow_utc(born, timezone)
    reference_dt_utc = to_arrow_utc(reference_dt, timezone)
    rdelta = relativedelta(reference_dt_utc.datetime, born_utc.datetime)
    if born_utc.datetime > reference_dt_utc.datetime:
        raise AgeValueError(
            'Reference date {} {} precedes DOB {} {}. Got {}'.format(
                reference_dt, str(reference_dt.tzinfo), born, timezone, rdelta))
    return rdelta


def formatted_age(born, reference_dt=None, timezone=None):
    if born:
        tzinfo = MyTimezone(timezone).tzinfo
        born = arrow.Arrow.fromdate(born, tzinfo=tzinfo).datetime
        reference_dt = reference_dt or get_utcnow()
        age_delta = age(born, reference_dt or get_utcnow())
        if born > reference_dt:
            return '?'
        elif age_delta.years == 0 and age_delta.months <= 0:
            return '%sd' % (age_delta.days)
        elif age_delta.years == 0 and age_delta.months > 0 and age_delta.months <= 2:
            return '%sm%sd' % (age_delta.months, age_delta.days)
        elif age_delta.years == 0 and age_delta.months > 2:
            return '%sm' % (age_delta.months)
        elif age_delta.years == 1:
            m = age_delta.months + 12
            return '%sm' % (m)
        elif age_delta.years > 1:
            return '%sy' % (age_delta.years)
        else:
            raise TypeError(
                'Age template tag missed a case... today - born. '
                'rdelta = {} and {}'.format(age_delta, born))


def get_age_in_days(reference_datetime, dob):
    age_delta = age(dob, reference_datetime)
    return age_delta.days


def convert_from_camel(name):
    """Converts from camel case to lowercase divided by underscores."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


class Convert(object):

    def __init__(self, value, convert=None, time_format=None):
        self.value = value
        self.convert = False if convert is False else True
        self.time_format = time_format or '%H:%M'

    def to_value(self):
        """Converts a string representation of a value into
        its original datatype.

        For dates and datetimes always returns a time zone
        aware datetime.
        """
        string_value = self.value.strip(' "')
        if self.convert:
            try:
                return self.to_time(string_value)
            except ConvertError:
                pass
            try:
                return self.to_boolean(string_value)
            except ConvertError:
                pass
            try:
                return self.to_decimal(string_value)
            except ConvertError:
                pass
            try:
                return self.to_int(string_value)
            except ConvertError:
                pass
            try:
                return self.to_datetime(string_value)
            except ConvertError:
                pass
        return string_value

    def to_string(self):
        try:
            string_value = self.value.isoformat()
            try:
                self.value.time()
                string_value = '{} {}'.format(
                    string_value, self.value.strftime(self.time_format))
            except AttributeError:
                pass
        except AttributeError:
            string_value = str(self.value)
        return string_value or force_str(self.value)

    def to_time(self, string_value):
        if re.match('^[0-9]{1,2}\:[0-9]{2}$', string_value):
            return string_value
        else:
            raise ConvertError()

    def to_boolean(self, string_value):
        if string_value.lower() in ['true', 'false', 'none']:
            return eval(string_value)
        else:
            raise ConvertError()

    def to_decimal(self, string_value):
        if '.' in string_value:
            try:
                value = Decimal(string_value)
                if str(value) == string_value:
                    return value
            except ValueError:
                pass
            except InvalidOperation:
                pass
        raise ConvertError()

    def to_int(self, string_value):
        try:
            value = int(string_value)
            if str(value) == string_value:
                return value
        except ValueError:
            pass
        raise ConvertError()
