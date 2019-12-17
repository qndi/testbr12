# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    bmd_export = fields.Boolean(string='Export to BMD required', copy=False)
    bmd_export_date = fields.Date(string='Last Export to BMD', copy=False)

    def write(self, vals):
        bmd_export_depends = ['property_account_receivable_id', 'property_account_payable_id', 'name', 'country_id', 'zip', 'city', 'street', 'vat',
                              'email']
        for record in self:
            if not record.bmd_export and 'bmd_export' not in vals:
                for field in vals:
                    if field in bmd_export_depends:
                        super(ResPartner, record).write({'bmd_export': True})
        return super(ResPartner, self).write(vals)
