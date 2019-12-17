# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import datetime

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase


class DpTimesheetContraints(TransactionCase):
    """
    Check Time Report constraints
    """

    def setUp(self):
        super().setUp()

        self.test_employee = self.env.ref('hr.employee_qdp')
        self.timesheet = self.env.ref('dp_hr.timesheet_qdp_1')
        self.manager = self.env.ref('base.user_admin')
        self.uid = self.env.ref('base.user_demo').id
        self.first_day = datetime.datetime(2018, 10, 1)

        # Neu Berechnen
        self.timesheet.action_recalculate()
        # Bestätigen
        self.timesheet.action_confirm()
        # Genehmigen
        self.timesheet.sudo(self.manager).action_approve()


    def test_create_actual_attendance(self):
        vals = {
            'check_in': self.first_day.replace(hour=10, minute=0, second=20),
            'check_out': self.first_day.replace(hour=12, minute=20, second=13),
            'employee_id': self.test_employee.id,
        }
        with self.assertRaises(ValidationError):
            self.env['hr.attendance'].create(vals)


    def test_modify_actual_attendance(self):
        a = self.env.ref('dp_hr.attendance_qdp_3')
        new_checkin = a.check_in.replace(second=44)
        with self.assertRaises(ValidationError):
            a.check_in = new_checkin


    def test_modify_contract(self):
        c1 = self.env.ref('dp_hr.contract_qdp_1')
        c1_manager = c1.sudo(self.manager)
        new_date_start = c1_manager.date_start.replace(day=2)
        with self.assertRaises(AccessError):
            c1.date_start = new_date_start

        c2 = self.env.ref('dp_hr.contract_qdp_2')
        c2_manager = c2.sudo(self.manager)
        new_date_start = c1_manager.date_start.replace(day=20)
        with self.assertRaises(ValidationError):
            c2_manager.date_start = new_date_start


    def test_modify_leave(self):
        holiday = self.env.ref('dp_hr.vacation_qdp_1')
        new_date_from = holiday.date_from.replace(day=21)
        with self.assertRaises(AccessError):
            holiday.date_from = new_date_from


    def test_modify_overtime_correction(self):
        with self.assertRaises(AccessError):
            self.env.ref('dp_hr.overtime_qdp_1').hours = 11


    def test_create_overtime_correction(self):
        DpOvertime = self.env['dp.overtime']
        DpOvertime_manager = DpOvertime.sudo(self.manager)

        # Create
        vals = {
            'name': 'Korrektur 1',
            'hours': 4,
            'date': self.first_day,
            'employee_id': self.test_employee.id,
        }
        with self.assertRaises(ValidationError):
            DpOvertime_manager.create(vals)
