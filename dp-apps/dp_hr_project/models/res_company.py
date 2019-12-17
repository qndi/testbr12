# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'


    suggest_remaining_time = fields.Boolean('Verbleibende Zeit beim Buchen vorschlagen')
