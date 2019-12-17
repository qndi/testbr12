# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    @api.onchange('date', 'employee_id', 'user_id')
    def onchange_date(self):
        if self.employee_id:
            employee = self.employee_id
        else:
            employee = self.env['hr.employee'].search([('user_id','=',self.env.user.id)], limit=1)
        if employee:
            domain = [
                ('timesheet_id.employee_id', '=', employee.id),
                ('date', '=', self.date),
            ]
            timesheet_day = self.env['dp.timesheet.day'].search(domain, limit=1)
            if timesheet_day:
                # A recalculate is required when it's the current day, because
                # the time changes every minute
                timesheet_day.calculate()
                company = timesheet_day.timesheet_id.employee_id.company_id
                if company.suggest_remaining_time:
                    self.unit_amount = timesheet_day.attendance_actual - timesheet_day.project_hours

    @api.model
    def create(self, vals):
        res = super().create(vals)

        res.recalculate_affected([res.date], [res.employee_id.id])

        return res


    def write(self, vals):
        # Recalculate affected days, both the old and new one of the old and
        # new employee
        days = set()
        employee_ids = set()

        for rec in self:
            days.add(rec.date)
            employee_ids.add(rec.employee_id.id)

        res = super().write(vals)

        for rec in self:
            days.add(rec.date)
            employee_ids.add(rec.employee_id.id)

        self.recalculate_affected(list(days), list(employee_ids))

        return res


    def unlink(self):
        # Recalculate affected days
        days = set()
        employee_ids = set()

        for rec in self:
            days.add(rec.date)
            employee_ids.add(rec.employee_id.id)

        res = super().unlink()

        self.recalculate_affected(list(days), list(employee_ids))

        return res


    @api.model
    def recalculate_affected(self, days, employee_ids):
        domain = [
            ('timesheet_id.employee_id', 'in', employee_ids),
            ('date', 'in', days),
        ]
        res = self.env['dp.timesheet.day'].search(domain)
        res.calculate()
