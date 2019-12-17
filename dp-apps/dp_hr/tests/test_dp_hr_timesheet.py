# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import datetime

from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase


class DpTimesheet(TransactionCase):
    """
    Check Time Reports values
    """

    def setUp(self):
        super().setUp()

        self.employee = self.env.ref('hr.employee_qdp')
        self.timesheet = self.env.ref('dp_hr.timesheet_qdp_1')
        self.manager = self.env.ref('base.user_admin')

        self.first_day = datetime.datetime(2018, 10, 1)


    def test_planned_attendance(self):
        """
        Check planned attendances on various days
        """

        expected = {
            # day: attendance

            # Monday
            1: 8.0,

            # Saturday
            6: 0.0,

            # Sunday
            7: 0.0,

            # Monday, new contract
            8: 7.0,

            # Saturday, sickness
            13: 0.0,

            # Monday, sickness
            15: 0.0,

            # Monday, holiday
            22: 0.0,
        }

        for date_day, expected_attendance in expected.items():
            day = self.timesheet.day_ids.filtered(lambda d: d.date.day == date_day)[0]
            assert day.attendance_planned == expected_attendance


    def test_create_employee(self):
        """
        Test automated creation of public holidays while creating a new employee

        There are public holidays on the 10. and 12..
        """

        vals = {
            'name': 'Max Mustermann',
        }
        new_emp = self.env['hr.employee'].create(vals)

        domain = [
            ('employee_id', '=', new_emp.id),
            ('name', '=like', 'Testfeiertag am %'),
        ]
        leaves_count = self.env['hr.leave'].search_count(domain)

        assert leaves_count == 2


    def test_import_public_holidays(self):
        """
        Import public holidays from a template

        There are public holidays on the 10. and 12..
        """

        # Since the employee was created by Odoo before our module was
        # loaded the import actually does something
        self.import_public_holidays()

        domain = [
            ('employee_id', '=', self.employee.id),
            ('name', '=like', 'Testfeiertag am %'),
        ]
        leaves_count = self.env['hr.leave'].search_count(domain)
        assert leaves_count == 2

        # Importing again won't create duplicates
        self.import_public_holidays()
        leaves_count_new = self.env['hr.leave'].search_count(domain)
        assert leaves_count == leaves_count_new


    def test_total_vacation(self):
        assert self.timesheet.vacation_new == 25
        assert self.timesheet.vacation_spent == 5
        assert self.timesheet.vacation_merged == 20
        assert self.timesheet.vacation_total == 20


    def test_timesheet_actual_attendance(self):
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 1).attendance_actual == 8
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 2).attendance_actual == 9
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 3).attendance_actual == 4
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 27).attendance_actual == 2


    def test_timesheet_travel_time(self):
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 4).travel_time == 2.0
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 5).travel_time == 0.0
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 6).travel_time == 2.0
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 7).travel_time == 0.0
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 13).travel_time == 15.0


    def test_timesheet_overtime(self):
        # Days
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 1).overtime_actual == 0
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 2).overtime_actual == 1
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 3).overtime_actual == -4
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 27).overtime_actual == 2

        # Timesheet
        assert self.timesheet.overtime_actual == -78.0


    def test_total_attendance(self):
        """
        Check the calculation of the sum of sicknesses

        There's a sickness from 13. to 15., however 13.
        and 14. are on a weekend.
        """

        assert self.timesheet.attendance_planned == 124.0
        assert self.timesheet.attendance_actual == 27.0


    def test_total_travel_time(self):
        """
        Check the calculation of the sum of travel time

        There are trips on 4., 6. and 13..

        dp-Österreich 1233: Gleitzeitanpassungen
        """

        assert self.timesheet.travel_time == 19.0


    def test_total_sickness(self):
        """
        Check the calculation of the sum of sicknesses

        There's a sickness from 13. to 15., however 13.
        and 14. are on a weekend.
        """

        assert self.timesheet.sickness_spent == 1


    def test_total_others(self):
        """
        Check the calculation of the sum of public holidays

        There are public holidays on the 10. and 12..
        """

        self.import_public_holidays()

        assert self.timesheet.others_spent == 2


    def test_total_overtime_correction(self):
        """
        Check the calculation of the sum of overtime corrections

        There's one correction.
        """

        assert self.timesheet.overtime_correction == 10


    def test_create_vacation_with_form(self):
        """
        When creating a vacation via the form (emulation) the expected values,
        those last seen on the form, are saved. The values don't change to
        zero or the current date.

        The vacation is deducted from the available vacation.

        dp-Österreich 1233: Gleitzeitanpassungen
        """

        assert self.timesheet.vacation_total == 20

        date_from = datetime.date(2018, 10, 18)
        date_to = datetime.date(2018, 10, 19)

        form = Form(self.env['hr.leave'], 'dp_hr.hr_leave_view_form_vacation')
        form.employee_id = self.employee
        form.holiday_status_id = self.env.ref('dp_hr.leave_type_vacation')
        form.request_date_from = date_from
        form.request_date_to = date_to
        leave = form.save()

        leave.sudo(self.manager).action_approve()

        assert leave.number_of_days == 2.0
        assert leave.number_of_days_display == 2.0
        assert leave.date_from.date() == date_from
        assert leave.date_to.date() == date_to
        assert leave.request_date_from == date_from
        assert leave.request_date_to == date_to

        assert self.timesheet.vacation_total == 18

        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 17).vacation_spent == 0
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 18).vacation_spent == 1
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 19).vacation_spent == 1
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 20).vacation_spent == 0


    def test_create_overlong_vacation(self):
        """
        Creating a vacation request for more than the available days is
        denied.

        dp-Österreich 1233: Gleitzeitanpassungen
        """

        form = Form(self.env['hr.leave'], 'dp_hr.hr_leave_view_form_vacation')
        form.employee_id = self.employee
        form.holiday_status_id = self.env.ref('dp_hr.leave_type_vacation')
        form.request_date_from = '2018-11-01'
        form.request_date_to = '2018-12-09'

        with self.assertRaisesRegex(ValidationError, 'The number of remaining leaves is not sufficient for this leave type'):
            form.save()



    def test_create_compensation_with_form(self):
        """
        When creating a compensation via the form (emulation) the expected
        values, those last seen on the form, are saved. The values don't
        change to zero or the current date.

        A compensation is marked as such on the day and doesn't have other
        effects. In particular the amount of vacation is untouched.

        dp-Österreich 1233: Gleitzeitanpassungen
        """

        assert self.timesheet.vacation_total == 20

        date = datetime.date(2018, 10, 19)

        form = Form(self.env['hr.leave'], 'dp_hr.hr_leave_view_form_vacation')
        form.employee_id = self.employee
        form.holiday_status_id = self.env.ref('hr_holidays.holiday_status_comp')
        form.request_date_from = date
        form.request_date_to = date
        leave = form.save()

        leave.sudo(self.manager).action_approve()

        assert leave.number_of_days == 1.0
        assert leave.number_of_days_display == 1.0
        assert leave.date_from.date() == date
        assert leave.date_to.date() == date
        assert leave.request_date_from == date
        assert leave.request_date_to == date

        assert self.timesheet.vacation_total == 20

        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 18).compensation_spent == 0
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 19).compensation_spent == 1
        assert self.timesheet.day_ids.filtered(lambda d: d.date.day == 20).compensation_spent == 0


    def import_public_holidays(self):
        vals = {
            'template_id': self.ref('dp_hr.leave_template_1'),
        }
        w = self.env['dp.leave.template.import'].create(vals)
        w.do_import()
