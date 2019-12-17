# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import fields, models


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'


    # Don't book vacation or compensation time on a project. This completes
    # the other part in __init__.py
    timesheet_generate = fields.Boolean(default=False)
    timesheet_project_id = fields.Many2one(default=False)
    timesheet_task_id = fields.Many2one(default=False)
