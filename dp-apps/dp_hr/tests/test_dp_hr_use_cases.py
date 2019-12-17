# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import datetime

from dateutil.relativedelta import relativedelta

from odoo.tests.common import TransactionCase


class DpTimesheetUseCases(TransactionCase):
    """ Werte des Timereports testen """

    def setUp(self):
        super().setUp()

        self.test_employee = self.env.ref('hr.employee_qdp')
        self.timesheet = self.env.ref('dp_hr.timesheet_qdp_1')

        self.first_day = datetime.datetime(2018, 10, 1)


    def test_timesheet_attendance_planned(self):
        # erster Montag (Weekday == 0)
        monday = self.timesheet.day_ids.filtered(lambda d: d.date.weekday() == 0)[0]
        assert monday.attendance_planned == 8

        self.env.ref('dp_hr.contract_qdp_1').unlink()

        # erster Montag (Weekday == 0)
        monday = self.timesheet.day_ids.filtered(lambda d: d.date.weekday() == 0)[0]
        assert monday.attendance_planned == 0


    def test_timesheet_attendance_actual(self):
        day = self.timesheet.day_ids.filtered(lambda d: d.date.day == 1)
        assert day.attendance_actual == 8
        assert day.overtime_actual == 0

        cin = self.env.ref('dp_hr.attendance_qdp_1').check_in
        new_cin = cin + relativedelta(hours=1)
        self.env.ref('dp_hr.attendance_qdp_1').check_in = new_cin

        day = self.timesheet.day_ids.filtered(lambda d: d.date.day == 2)
        assert day.attendance_actual == 9
        assert day.overtime_actual == 1


    def test_timesheet_modify_vacation(self):
        # MO-FR innerhalb des Urlaubs
        day = self.timesheet.day_ids.filtered(lambda d: d.date.day >= 20 and d.date.weekday() < 5)[0]
        assert day.vacation_spent == 1

        # change Holiday from 20. to 23.
        v = self.env.ref('dp_hr.vacation_qdp_1')
        new_date_from = v.date_from.replace(day=23)
        v.date_from = new_date_from

        day = self.timesheet.day_ids.filtered(lambda d: d.date.day >= 20 and d.date.weekday() < 5)[0]
        assert day.vacation_spent == 0


    def test_timesheet_unlink_vacation(self):
        # MO-FR innerhalb des Urlaubs
        day = self.timesheet.day_ids.filtered(lambda d: d.date.day >= 20 and d.date.weekday() < 5)[0]
        assert day.vacation_spent == 1

        leave = self.env.ref('dp_hr.vacation_qdp_1')
        leave.action_refuse()
        leave.action_draft()
        leave.unlink()

        day = self.timesheet.day_ids.filtered(lambda d: d.date.day >= 20 and d.date.weekday() < 5)[0]
        assert day.vacation_spent == 0


    def test_timesheet_add_vacation(self):
        # MO-FR innerhalb des Urlaubs
        day = self.timesheet.day_ids.filtered(lambda d: d.date.day >= 1 and d.date.weekday() < 5)[0]
        assert day.vacation_spent == 0

        vals = {
            'name': 'test_vacation',
            'date_from': day.date,
            'date_to': day.date,
            'employee_id': self.env.user.id,
            'holiday_status_id': self.ref('dp_hr.leave_type_vacation'),
        }
        v = self.env['hr.leave'].create(vals)
        v.action_approve()

        day = self.timesheet.day_ids.filtered(lambda d: d.date.day >= 1 and d.date.weekday() < 5)[0]
        assert day.vacation_spent == 0


    def test_timesheet_modify_overtime_correction(self):
        assert self.timesheet.overtime_correction == 10

        c = self.env.ref('dp_hr.overtime_qdp_1')
        c.hours = 11

        assert self.timesheet.overtime_correction == 11


    def test_timesheet_unlink_overtime_correction(self):
        assert self.timesheet.overtime_correction == 10

        self.env.ref('dp_hr.overtime_qdp_1').unlink()

        assert self.timesheet.overtime_correction == 0
