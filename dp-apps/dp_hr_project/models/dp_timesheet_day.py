# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import fields, models
from odoo.addons import decimal_precision as dp


class DpTimesheetDay(models.Model):
    _inherit = 'dp.timesheet.day'


    project_hours = fields.Float('Projektzeiten', digits=dp.get_precision('HR Time'))
    chargeable_hours = fields.Float('Chargeable', digits=dp.get_precision('HR Time'))
    billable_hours = fields.Float('Billable', digits=dp.get_precision('HR Time'))


    def calculate(self):
        super().calculate()

        for record in self:
            vals = {
                'project_hours': 0.0,
                'chargeable_hours': 0.0,
                'billable_hours': 0.0,
            }

            domain = [
                ('employee_id', '=', record.timesheet_id.employee_id.id),
                ('date', '=', record.date),
            ]
            for line in self.env['account.analytic.line'].search(domain):
                vals['project_hours'] += line.unit_amount
                vals['chargeable_hours'] += line.unit_amount if line.project_id.is_chargeable else 0.0
                vals['billable_hours'] += line.unit_amount if line.so_line else 0.0

            # Only write values that changed, don't rewrite all values. That
            # allows to calculate approved timesheets. The billable_hours may
            # change afterwards if the customer disputes the billability of
            # certain tasks.
            vals = record.get_changed_values(vals)
            if vals:
                record.write(vals)
