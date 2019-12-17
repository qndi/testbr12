# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import fields, models


class DpTimesheetWarning(models.Model):
    _name = 'dp.timesheet.warning'
    _description = 'Warnung in Zeiterfassung'


    timesheet_id = fields.Many2one('dp.timesheet', 'Time Report', required=True,
        ondelete='cascade')
    date = fields.Date('Datum')
    description = fields.Char('Beschreibung')
