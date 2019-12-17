# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    bmd_tax_code = fields.Char(string='BMD-Steuercode')
