# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import fields, models


class DpLeaveTemplateImport(models.TransientModel):
    _name = 'dp.leave.template.import'
    _description = 'Feiertagsimport'


    def _default_template_id(self):
        return self.env['dp.leave.template'].search([], limit=1)


    def _default_employee_ids(self):
        return self.env['hr.employee'].search([])


    template_id = fields.Many2one('dp.leave.template', 'Feiertagsvorlage', required=True, default=_default_template_id)
    employee_ids = fields.Many2many('hr.employee', string='Mitarbeiter', required=True, default=_default_employee_ids)


    def do_import(self):
        self.ensure_one()

        HrLeave = self.env['hr.leave']

        company = self.env['dp.timesheet'].get_company()
        new_leave_ids = []

        for employee in self.employee_ids:
            for line in self.template_id.line_ids:
                domain = [
                    ('employee_id', '=', employee.id),
                    ('date_from', '=', line.date),
                    ('date_to', '=', line.date),
                    ('holiday_status_id', '=', company.leave_type_public_holiday.id),
                ]
                if HrLeave.search_count(domain):
                    continue

                vals = {
                    'employee_id': employee.id,
                    'date_from': line.date,
                    'date_to': line.date,
                    'request_date_from': line.date,
                    'request_date_to': line.date,
                    'number_of_days': 1,
                    'holiday_status_id': company.leave_type_public_holiday.id,
                    'name': line.name,
                    'state': 'validate',
                }
                new_leave_ids.append(HrLeave.create(vals).id)

        action = self.env.ref('dp_hr.open_public_holiday').read()[0]
        action['domain'] = [('id', 'in', new_leave_ids)]
        action['context'] = {'only_public_holidays': 1}

        return action
