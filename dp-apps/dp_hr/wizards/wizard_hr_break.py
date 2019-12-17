# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from datetime import timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class WizardHrBreak(models.TransientModel):
    _name = 'wizard.hr.break'
    _description = 'Pause eintragen'


    def _default_date(self):
        user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
        utcoffset = user_tz.localize(fields.Datetime.now()).utcoffset()
        now = fields.Datetime.now()
        noon = now.replace(hour=12, minute=00, second=00) - utcoffset
        return noon


    date = fields.Datetime('Zeitpunkt', default=_default_date)
    duration = fields.Float('Dauer', default=1.0)


    @api.constrains('duration')
    def check_duration(self):
        if self.duration and self.duration > 4.0:
            raise ValidationError(_('Die Dauer kann max. 4h betragen.'))


    def process_break(self):
        self.ensure_one()

        HrAttendance = self.env['hr.attendance']

        domain = [
            ('employee_id.user_id', '=', self.env.user.id),
            ('check_in', '<', self.date),
            '|',
            ('check_out', '=', False),
            ('check_out', '>', self.date + timedelta(hours=self.duration)),
        ]
        attendances = HrAttendance.search(domain, order='check_in DESC')
        attendance = attendances and attendances[0]
        if attendance:
            if not attendance.check_out:
                attendance.write({'check_out': self.date})
                new_attendance_id = HrAttendance.create({
                    'employee_id': attendance.employee_id.id,
                    'check_in': self.date + timedelta(hours=self.duration),
                })
            else:
                check_out = attendance.check_out
                attendance.check_out = self.date
                new_attendance_id = HrAttendance.create({
                    'employee_id': attendance.employee_id.id,
                    'check_in': self.date + timedelta(hours=self.duration),
                    'check_out': check_out,
                })
        else:
            raise ValidationError(_('Zu diesem Zeitpunkt kann keine Pause '
                'eingetragen werden. Bitte erstellen Sie die Pause manuell.'))

        action = self.env.ref('hr_attendance.hr_attendance_action').read()[0]
        action['domain'] = [('id', 'in', [attendance.id, new_attendance_id.id])]
        action['context'] = {'search_default_today': 0}

        return action
