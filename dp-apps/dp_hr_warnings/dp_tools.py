# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import calendar
from datetime import date, datetime, timedelta, tzinfo

from odoo import tools as odoo_tools


# Action to show the form view of the related model for the Odoo addon
# connector. For use with the related_action decorator from there.
def related_form_action(session, job, model):
    return {
        'view_type': 'form',
        'view_mode': 'form',
        'res_model': model,
        'type':      'ir.actions.act_window',
        'res_id':    job.args[0],
    }


# From the section about datetime.datetime in the chapter about the datetime
# module in the Python documentation
#
# We use this and not the pytz module since the latter is strange. It's docs
# even say "Unfortunately using the tzinfo argument of the standard datetime
# constructors ''does not work'' with pytz for many timezones."
# The examples given below the code of GMT1 in the Python docs create this
# result with pytz 2012c-1ubuntu0.1, there's no difference between DST and
# normal:
# >>> import pytz
# >>> from datetime import timedelta, datetime, tzinfo
# >>> tz_v = pytz.timezone('Europe/Vienna')
# >>> dt1 = datetime(2006, 11, 21, 16, 30, tzinfo=tz_v)
# >>> dt1.dst()
# datetime.timedelta(0)
# >>> dt1.utcoffset()
# datetime.timedelta(0, 3600)
# >>> dt2 = datetime(2006, 6, 14, 13, 0, tzinfo=tz_v)
# >>> dt2.dst()
# datetime.timedelta(0)
# >>> dt2.utcoffset()
# datetime.timedelta(0, 3600)
#
# The more recent version 2015.7 installed with pip into a virtualenv is even
# more strange:
# >>> import pytz
# >>> from datetime import timedelta, datetime, tzinfo
# >>> tz_v = pytz.timezone('Europe/Vienna')
# >>> dt1 = datetime(2006, 11, 21, 16, 30, tzinfo=tz)
# >>> dt1 = datetime(2006, 11, 21, 16, 30, tzinfo=tz_v)
# >>> dt1.dst()
# datetime.timedelta(0)
# >>> dt1.utcoffset()
# datetime.timedelta(0, 3900)
# >>> dt2 = datetime(2006, 6, 14, 13, 0, tzinfo=tz_v)
# >>> dt2.dst()
# datetime.timedelta(0)
# >>> dt2.utcoffset()
# datetime.timedelta(0, 3900)

class GMT1(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=1) + self.dst(dt)


    def dst(self, dt):
        # DST starts last Sunday in March
        d = datetime(dt.year, 4, 1, 3)
        self.dston = d - timedelta(days=d.weekday() + 1)
        # ends last Sunday in October
        d = datetime(dt.year, 11, 1, 3)
        self.dstoff = d - timedelta(days=d.weekday() + 1)

        if self.dston <= dt.replace(tzinfo=None) < self.dstoff:
            return timedelta(hours=1)

        return timedelta(0)


    def tzname(self, dt):
        return 'GMT+1'


tz_GMT1 = GMT1()

class UTC(tzinfo):
    def utcoffset(self, dt):
        return timedelta(0)


    def dst(self, dt):
        return timedelta(0)


    def tzname(self, dt):
        return 'UTC'


tz_UTC = UTC()


# Convert an Odoo Datetime field into a Python datetime.datetime object which
# is timezone-aware and at GMT+1
def convert_datetime_gmt1(odoo_datetime):
    dt = odoo_datetime.replace(tzinfo=tz_UTC)
    dt = dt.astimezone(tz_GMT1)
    return dt


# Format an Odoo Date field into a string with german style
def format_date(odoo_date):
    # Odoo supports formating dates, is that part of a widget, or can we use
    # it here?
    return odoo_date.strftime('%d.%m.%Y')


# Format an Odoo Datetime field into a string with german style
# odoo_datetime has to be in UTC, the result will be in GMT+1
def format_datetime(odoo_datetime):
    dt = convert_datetime_gmt1(odoo_datetime)
    return dt.strftime('%d.%m.%Y %H:%M:%S')


# Format the current date into a string with german style
def format_date_now():
    return date.today().strftime('%d.%m.%Y')


# Format the current date and time into a string with german style
def format_datetime_now():
    return datetime.now(tz_GMT1).strftime('%d.%m.%Y %H:%M:%S')


# Format the given POSIX timestamp, such as is returned by time.time(), into
# a string with german style
def format_timestamp(ts):
    return datetime.fromtimestamp(float(ts), tz_GMT1).strftime('%d.%m.%Y %H:%M:%S')


# Convert a Python datetime.date object into an Odoo Date field string
def make_odoo_date(date):
    return datetime.strftime(date, odoo_tools.DEFAULT_SERVER_DATE_FORMAT)


# Convert a Python datetime.datetime object into an Odoo Datetime field string
def make_odoo_datetime(dt):
    return datetime.strftime(dt, odoo_tools.DEFAULT_SERVER_DATETIME_FORMAT)


# dt must be a timezone-aware Python datetime.datetime object at GMT+1.
# A new datetime.datetime object is created, the time set to 00:00 while
# still at GMT+1, then shifted to UTC and returned.
def gmt1_to_utc_midnight(dt):
    assert dt.tzinfo is tz_GMT1
    dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    dt = dt.astimezone(tz_UTC)
    return dt


# Convert a string formatted as an ISO-8601 date and time in the timezone
# given by tzinfo into an Odoo datetime field
def iso_8601_to_odoo(iso, tzinfo=tz_GMT1):
    dt = datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S')
    dt = dt.replace(tzinfo=tzinfo)
    dt = dt.astimezone(tz_UTC)
    return make_odoo_datetime(dt)


# Convert a string formatted as an ISO-8601 date, apply the given time,
# consider the result to be in the timezone given by tzinfo and return
# an Odoo datetime field
def iso_8601_date_to_odoo(iso, hour=0, minute=0, second=0, microsecond=0, tzinfo=tz_GMT1):
    dt = datetime.strptime(iso, '%Y-%m-%d')
    dt = dt.replace(hour=hour, minute=minute, second=second,
        microsecond=microsecond, tzinfo=tzinfo)
    dt = dt.astimezone(tz_UTC)
    return make_odoo_datetime(dt)


def last_day_of_previous_month(date):
    """
    Given a datetime.date return a new datetime.date representing the last
    day of the previous month.
    """

    date = date.replace(day=1)
    return date - timedelta(days=1)


def first_day_of_previous_month(date):
    """
    Given a datetime.date return a new datetime.date representing the first
    day of the previous month.
    """

    date = last_day_of_previous_month(date)
    return date.replace(day=1)


def first_day_of_current_month():
    """
    Return a datetime.date representing the first day of the current month
    """

    return date.today().replace(day=1)


def last_day_of_current_month():
    """
    Return a datetime.date representing the last day of the current month
    """

    today = date.today()
    return today.replace(day=calendar.monthrange(today.year, today.month)[1])


def day_of_the_week_short(date):
    """
    Return the weekday of the given date in short format
    e.g. Mo, Di, Mi
    """

    weekday = {
        0: 'Mo',
        1: 'Di',
        2: 'Mi',
        3: 'Do',
        4: 'Fr',
        5: 'Sa',
        6: 'So',
    }

    return weekday[date.weekday()]


def format_time(float_time):
    """
    Format an Odoo float time into a string with hours and minutes.
    Negative values are supported.
    """

    sign = '-' if float_time < 0 else ''
    hours = abs(int(float_time))
    minutes = abs(float_time) - hours
    minutes /= 100
    minutes *= 60
    minutes *= 100
    minutes = int(minutes)
    return '%s%d:%02d' % (sign, hours, minutes)
