# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    bmd_export = fields.Boolean(string='Export to BMD required', copy=False)
    bmd_export_date = fields.Date(string='Last Export to BMD', copy=False)

    @api.multi
    def action_invoice_open(self):
        self.bmd_export = True
        if not self.partner_id.commercial_partner_id.bmd_export_date:
            self.partner_id.commercial_partner_id.bmd_export = True
        return super(AccountInvoice, self).action_invoice_open()
