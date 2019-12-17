# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import datetime

from odoo.tests.common import TransactionCase


class DpHrWarnings(TransactionCase):
    """
    Check Warning features
    """

    def setUp(self):
        super().setUp()

        env = self.env

        self.employee = env.ref('hr.employee_qdp')
        self.timesheet = env.ref('dp_hr.timesheet_qdp_1')
        self.manager = env.ref('base.user_admin')
        self.uid = env.ref('base.user_demo').id
        self.first_day = datetime.date(2018, 10, 1)


    def test_work_on_absent_warning_vacation(self):
        """
        The employee is on vacation from 20. to 26., thus a warning appears
        for attendance during that time.

        The attendance on 27., saturday, is part of the demo data, thus the
        warning about attendance on the weekend is always there. Other
        warnings do not appear.

        dp-Österreich 1555: dp_hr Tests
        """

        vals = {
            'check_in': datetime.datetime(2018, 10, 22, 9),
            'check_out': datetime.datetime(2018, 10, 22, 10),
            'employee_id': self.employee.id,
        }
        self.env['hr.attendance'].create(vals)

        self.timesheet.check_warnings()

        expected = [
            (datetime.date(2018, 10, 22), 'Arbeitszeit an einem Urlaubs-, Feier- und Krankenstandstag'),
            (datetime.date(2018, 10, 27), 'Arbeitszeit am Wochenende'),
        ]
        self.compare_warnings(expected)


    def test_work_on_absent_warning_public_holiday(self):
        """
        There's a public holiday on 10., thus a warning appears for attendance
        on that day.

        The attendance on 27., saturday, is part of the demo data, thus the
        warning about attendance on the weekend is always there. Other
        warnings do not appear.

        dp-Österreich 1555: dp_hr Tests
        """

        # Import public holidays template
        vals = {
            'template_id': self.ref('dp_hr.leave_template_1'),
        }
        w = self.env['dp.leave.template.import'].sudo(self.manager).create(vals)
        w.do_import()

        # Create attendance
        vals = {
            'check_in': datetime.datetime(2018, 10, 10, 9),
            'check_out': datetime.datetime(2018, 10, 10, 10),
            'employee_id': self.employee.id,
        }
        self.env['hr.attendance'].create(vals)

        self.timesheet.check_warnings()

        expected = [
            (datetime.date(2018, 10, 10), 'Arbeitszeit an einem Urlaubs-, Feier- und Krankenstandstag'),
            (datetime.date(2018, 10, 27), 'Arbeitszeit am Wochenende'),
        ]
        self.compare_warnings(expected)


    def test_work_on_absent_warning_sickness(self):
        """
        The employee is sick from 13. to 15., thus a warning appears
        for attendance during that time.

        The attendance on 27., saturday, is part of the demo data, thus the
        warning about attendance on the weekend is always there. Other
        warnings do not appear.

        dp-Österreich 1555: dp_hr Tests
        """

        vals = {
            'check_in': datetime.datetime(2018, 10, 15, 9),
            'check_out': datetime.datetime(2018, 10, 15, 10),
            'employee_id': self.employee.id,
        }
        self.env['hr.attendance'].create(vals)

        self.timesheet.check_warnings()

        expected = [
            (datetime.date(2018, 10, 15), 'Arbeitszeit an einem Urlaubs-, Feier- und Krankenstandstag'),
            (datetime.date(2018, 10, 27), 'Arbeitszeit am Wochenende'),
        ]
        self.compare_warnings(expected)


    def test_work_on_weekends_warning(self):
        """
        The attendance on 27., saturday, causes a warning about attendance
        on the weekend. Other warnings do not appear. In particular there is
        no warning about the long travel time on 13..

        dp-Österreich 1233: Gleitzeitanpassungen
        """

        self.timesheet.check_warnings()

        expected = [
            (datetime.date(2018, 10, 27), 'Arbeitszeit am Wochenende'),
        ]
        self.compare_warnings(expected)


    def test_early_working_warning(self):
        """
        Attendance before 6:00 CEST causes a warning.

        The attendance on 27., saturday, is part of the demo data, thus the
        warning about attendance on the weekend is always there. Other
        warnings do not appear.

        dp-Österreich 1555: dp_hr Tests
        """

        vals = {
            'check_in': datetime.datetime(2018, 10, 19, 3),
            'check_out': datetime.datetime(2018, 10, 19, 8),
            'employee_id': self.employee.id,
        }
        self.env['hr.attendance'].create(vals)

        self.timesheet.check_warnings()

        expected = [
            (datetime.date(2018, 10, 19), 'Arbeitsbeginn vor 6:00 Uhr'),
            (datetime.date(2018, 10, 27), 'Arbeitszeit am Wochenende'),
        ]
        self.compare_warnings(expected)


    def test_late_working_warning(self):
        """
        Attendance after 20:00 CEST causes a warning.

        The attendance on 27., saturday, is part of the demo data, thus the
        warning about attendance on the weekend is always there. Other
        warnings do not appear.

        dp-Österreich 1555: dp_hr Tests
        """

        vals = {
            'check_in': datetime.datetime(2018, 10, 19, 20),
            'check_out': datetime.datetime(2018, 10, 19, 21),
            'employee_id': self.employee.id,
        }
        self.env['hr.attendance'].create(vals)

        self.timesheet.check_warnings()

        expected = [
            (datetime.date(2018, 10, 19), 'Arbeitsende nach 20:00 Uhr'),
            (datetime.date(2018, 10, 27), 'Arbeitszeit am Wochenende'),
        ]
        self.compare_warnings(expected)


    def test_check_working_too_long_warning_break(self):
        """
        Attendance of more than 6 hours without a break causes a warning.

        The attendance on 27., saturday, is part of the demo data, thus the
        warning about attendance on the weekend is always there. Other
        warnings do not appear.

        dp-Österreich 1555: dp_hr Tests
        """

        vals = {
            'check_in': datetime.datetime(2018, 10, 19, 7),
            'check_out': datetime.datetime(2018, 10, 19, 14),
            'employee_id': self.employee.id,
        }
        self.env['hr.attendance'].create(vals)

        self.timesheet.check_warnings()

        expected = [
            (datetime.date(2018, 10, 19), 'Die maximale Arbeitszeit (6:00) ohne ausreichende Pause (min. 0:30) wurde überschritten (7:00)'),
            (datetime.date(2018, 10, 27), 'Arbeitszeit am Wochenende'),
        ]
        self.compare_warnings(expected)


    def test_check_working_too_long_warning_total(self):
        """
        Attendance of more than 10 hours on a day causes a warning.

        The attendance on 27., saturday, is part of the demo data, thus the
        warning about attendance on the weekend is always there. Other
        warnings do not appear.

        dp-Österreich 1555: dp_hr Tests
        """

        vals_list = [
            {
                'check_in': datetime.datetime(2018, 10, 19, 4, 0),
                'check_out': datetime.datetime(2018, 10, 19, 9, 30),
                'employee_id': self.employee.id,
            },
            {
                'check_in': datetime.datetime(2018, 10, 19, 11, 0),
                'check_out': datetime.datetime(2018, 10, 19, 16, 30),
                'employee_id': self.employee.id,
            },
        ]
        self.env['hr.attendance'].create(vals_list)

        self.timesheet.check_warnings()

        expected = [
            (datetime.date(2018, 10, 19), 'Die maximale Arbeitszeit pro Tag (10:00) wurde überschritten (11:00)'),
            (datetime.date(2018, 10, 27), 'Arbeitszeit am Wochenende'),
        ]
        self.compare_warnings(expected)


    def compare_warnings(self, expected):
        assert len(self.timesheet.warning_ids) == len(expected)

        for actual, expected in zip(self.timesheet.warning_ids, expected):
            assert actual.date == expected[0]
            assert actual.description == expected[1]
