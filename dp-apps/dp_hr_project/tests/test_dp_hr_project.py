# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import datetime

from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tests.common import TransactionCase


class DpHrProject(TransactionCase):
    """
    Check Project features
    """

    def setUp(self):
        super().setUp()

        env = self.env

        self.employee = env.ref('hr.employee_qdp')
        self.timesheet = env.ref('dp_hr.timesheet_qdp_1')
        self.manager = env.ref('base.user_admin')
        self.uid = env.ref('base.user_demo').id
        self.first_day = datetime.date(2018, 10, 1)

        # These are probably created automatically by confirming a SO and
        # thus don't have an XML-Id
        domain = [
            ('sale_line_id', '=', env.ref('sale_timesheet.sale_line_13').id),
        ]
        self.chargeable_project = env['project.project'].search(domain)[0]
        self.chargeable_task = env['project.task'].search(domain)[0]


    def test_suggest_remaining_time(self):
        """
        The appropriate remaining time is suggested when creating a new
        time record.

        On 1. 10. Marc Demo has two hours of attendance that aren't yet
        assigned to a project.

        dp-Österreich 802: dp_hr_project Portierung Odoo 12
        """

        form = Form(self.env['account.analytic.line'],
            'hr_timesheet.hr_timesheet_line_tree')
        form.date = self.first_day
        form.employee_id = self.employee

        # We could assert on form.unit_amount directly, but it's hoped that
        # actually creating the record will trigger additional processing
        # that might be there and could alter the value again which would be
        # detected then. This happens e. g. with the so_line field.
        form.project_id = self.chargeable_project
        form.task_id = self.chargeable_task
        form.name = 'foo'
        line = form.save()
        assert line.unit_amount == 2.0


    def test_approved_timesheet(self):
        """
        An approved timesheet is immutable with the fields billable_hours
        and billability being excepted from that.

        dp-Österreich 802: dp_hr_project Portierung Odoo 12
        """

        self.timesheet.action_confirm()
        self.timesheet.action_approve()

        # Initial situation
        assert self.timesheet.project_hours == 8.0
        assert self.timesheet.chargeable_hours == 6.0
        assert self.timesheet.chargeability == 5.0
        assert self.timesheet.billable_hours == 4.0
        assert self.timesheet.billability == 3.0

        # Make something non-billable. Only the billable_hours and the
        # billability change.
        line = self.env.ref('dp_hr_project.aal_qdp_1')
        # Modification of approved timesheets requires extra permission
        line = line.sudo()
        line.so_line = False

        assert self.timesheet.project_hours == 8.0
        assert self.timesheet.chargeable_hours == 6.0
        assert self.timesheet.chargeability == 5.0
        assert self.timesheet.billable_hours == 0.0
        assert self.timesheet.billability == 0.0

        # It's not possible to change the amount of booked time
        with self.assertRaisesRegex(ValidationError, 'Der Time Report .* ist nicht mehr offen'):
            line.unit_amount = 5.0


    def test_leave_without_project_time(self):
        """
        Creating a leave doesn't book that time on a project.

        dp-Österreich 1233: Gleitzeitanpassungen
        """

        assert self.timesheet.project_hours == 8.0

        # The undesired behavior happens somewhere in the code normally
        # called by the frontend, thus we must use the form emulation to
        # make the test fail when it should.
        form = Form(self.env['hr.leave'])
        form.name = 'ZA'
        form.holiday_status_id = self.env.ref('hr_holidays.holiday_status_comp')
        form.date_from = '2018-10-19'
        form.date_to = '2018-10-19'
        form.request_date_from = '2018-10-19'
        form.request_date_to = '2018-10-19'
        form.number_of_days = 1
        form.employee_id = self.employee
        leave = form.save()

        leave.sudo(self.manager).action_approve()

        assert self.timesheet.project_hours == 8.0


    def test_approve_timesheet_with_validation_date(self):
        """
        Approving a timesheet sets the validation date in the employee,
        opening the sheet again resets it.

        dp-Österreich 1500: dp_hr_project: Zeitbuchungen bestätigen
        """

        assert self.employee.timesheet_validated is False

        self.timesheet.action_confirm()
        self.timesheet.action_approve()

        assert self.employee.timesheet_validated == datetime.date(2018, 10, 31)

        self.timesheet.action_open()

        assert self.employee.timesheet_validated is False
