# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

import datetime

import pytz

from odoo import api, fields, models, _

from .. import dp_tools


class DpTimesheet(models.Model):
    _inherit = 'dp.timesheet'


    warning_ids = fields.One2many('dp.timesheet.warning', 'timesheet_id', 'Warnungen')
    date_last_check = fields.Datetime('Datum letzte Prüfung', default=datetime.datetime.min,
        required=True, help='Datum der letzten Überprüfung des Timesheets auf Warnungen')
    button_check = fields.Boolean(compute='_compute_button_check')


    def _compute_button_check(self):
        for record in self:
            # After checking date_last_check is set to the value returned
            # by fields.Datetime.now(). It will always return a value with
            # zero microseconds. The write_date is set by the DB and includes
            # microseconds. Thus we have to allow a delta. This also covers
            # the time taken by the checks.
            delta = record.write_date - record.date_last_check
            delta = abs(delta.total_seconds())
            record.button_check = True if delta < 5 else False


    def check_warnings(self):
        for record in self:
            # remove old warnings
            record.warning_ids.unlink()

            # new warnings
            warnings = []

            user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
            for day in record.day_ids:
                # In order to check if DST is active assume UTC noon as the
                # time component
                check_ts = datetime.datetime.combine(day.date, datetime.time(12, 0))
                utcoffset = user_tz.localize(check_ts).utcoffset()

                next_day = day.date + datetime.timedelta(days=1)

                # Due to the constraint check_out is either unset or within
                # the day of check_in. Thus there's no need for an explicit
                # check.
                domain = [
                    ('employee_id', '=', record.employee_id.id),
                    ('check_in', '>=', day.date),
                    ('check_in', '<', next_day),
                    ('is_travel_time', '!=', True),
                ]
                attendances = self.env['hr.attendance'].search(domain, order='check_in')
                if not attendances:
                    continue

                work_on_absent_warning = self.check_work_on_absent_warning(day)
                work_on_weekends_warning = self.check_work_on_weekends_warning(day)
                first_check_in = attendances[0].check_in + utcoffset
                early_working_warning = self.check_early_working_warning(day, first_check_in)

                last_check_out = attendances[len(attendances) - 1].check_out
                if not last_check_out:
                    last_check_out = fields.Datetime.now()
                last_check_out = last_check_out + utcoffset
                late_working_warning = self.check_late_working_warning(day, last_check_out)
                working_too_many_hours_warnings = self.check_working_too_long_warnings(day, attendances)

                if work_on_absent_warning:
                    warnings.append(work_on_absent_warning)
                if work_on_weekends_warning:
                    warnings.append(work_on_weekends_warning)
                if early_working_warning:
                    warnings.append(early_working_warning)
                if late_working_warning:
                    warnings.append(late_working_warning)
                if working_too_many_hours_warnings:
                    warnings.extend(working_too_many_hours_warnings)

            record.warning_ids = warnings
            record.date_last_check = fields.Datetime.now()

        return True


    @api.model
    def check_work_on_absent_warning(self, day):
        # if work on absent day > warning
        if day.attendance_actual > 0 and day.timesheet_id.employee_id.company_id.warning_work_on_absent and \
                (day.vacation_spent > 0 or day.sickness_spent > 0 or day.others_spent > 0):
            return (0, 0, {
                'description': _('Arbeitszeit an einem Urlaubs-, Feier- und Krankenstandstag'),
                'date': day.date,
            })

        return None

    @api.model
    def check_work_on_weekends_warning(self, day):
        # if work on weekends > warning
        if day.date.isoweekday() in (6, 7) and day.attendance_actual > 0 and \
                day.timesheet_id.employee_id.company_id.warning_work_on_weekends:
            return (0, 0, {
                'description': _('Arbeitszeit am Wochenende'),
                'date': day.date,
            })

        return None

    @api.model
    def check_early_working_warning(self, day, first_check_in):
        # starting work too early > warning
        company = day.timesheet_id.employee_id.company_id

        earliest_work_begin = datetime.datetime.combine(day.date, datetime.time())
        earliest_work_begin += datetime.timedelta(seconds=company.earliest_work_begin * 3600)

        if first_check_in < earliest_work_begin:
            real_hour = dp_tools.format_time(company.earliest_work_begin)
            return (0, 0, {
                'description': _('Arbeitsbeginn vor %s Uhr') % real_hour,
                'date': day.date,
            })

        return None

    @api.model
    def check_late_working_warning(self, day, last_check_out):
        # working too late > warning
        company = day.timesheet_id.employee_id.company_id

        latest_work_end = datetime.datetime.combine(day.date, datetime.time())
        latest_work_end += datetime.timedelta(seconds=company.latest_work_end * 3600)

        if last_check_out > latest_work_end:
            real_hour = dp_tools.format_time(company.latest_work_end)
            return (0, 0, {
                'description': _('Arbeitsende nach %s Uhr') % real_hour,
                'date': day.date,
            })

        return None

    @api.model
    def check_working_too_long_warnings(self, day, attendances):
        warnings = []
        company_id = day.timesheet_id.employee_id.company_id
        sum_work = work_on_day = 0.0
        max_work_without_break = False
        for idx, attendance in enumerate(attendances):
            check_in = attendance.check_in
            if attendance.check_out:
                check_out = attendance.check_out
            elif check_in.date() == fields.Date.today():
                check_out = fields.Datetime.now()
            else:
                check_out = (check_in + datetime.timedelta(days=1)).date()
                check_out = datetime.datetime.fromordinal(check_out.toordinal())
            delta = check_out - check_in
            if idx:
                delta_break = attendance.check_in - attendances[idx - 1].check_out
                delta_break = delta_break.total_seconds() / 3600
                if delta_break >= company_id.min_break_in_hours:
                    sum_work = 0.0

            hours = delta.total_seconds() / 3600
            sum_work += hours
            work_on_day += hours
            # too many working hours without break > warning
            if sum_work > company_id.max_work_without_break and not max_work_without_break:
                max_work_without_break = True  # sorgt dafür, dass diese Warnung nur einmal pro Tag auftritt
                warnings.append((0, 0, {
                    'description': _(
                        'Die maximale Arbeitszeit (%s) ohne ausreichende Pause (min. %s) wurde überschritten (%s)') % (
                            dp_tools.format_time(company_id.max_work_without_break),
                            dp_tools.format_time(company_id.min_break_in_hours),
                            dp_tools.format_time(sum_work),
                        ),
                    'date': day.date,
                }))

        # too many working hours > warning
        if work_on_day > company_id.max_work_per_day:
            warnings.append((0, 0, {
                'description': _('Die maximale Arbeitszeit pro Tag (%s) wurde überschritten (%s)') % (
                    dp_tools.format_time(company_id.max_work_per_day),
                    dp_tools.format_time(work_on_day),
                ),
                'date': day.date,
            }))

        return warnings
