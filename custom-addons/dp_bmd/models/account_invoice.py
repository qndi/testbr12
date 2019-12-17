# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    bmd_export = fields.Boolean(string='Export to BMD required', copy=False)
    bmd_export_date = fields.Date(string='Last Export to BMD', copy=False)

    @api.multi
    def action_invoice_open(self):
        for record in self:
            partner_id = record.partner_id.commercial_partner_id

            record.bmd_export = True
            if not partner_id.bmd_export_date:
                partner_id.bmd_export = True

            # Account Receivable
            standard_debit_account_id = partner_id.default_get(partner_id._fields).get('property_account_receivable_id')
            standard_debit_account = record.env['account.account'].browse(standard_debit_account_id)

            if record.type in ['out_invoice', 'out_refund']:
                if record.env.user.company_id.create_bmd_debit_account == 'on_first_invoice' and partner_id.customer:
                    if standard_debit_account_id == partner_id.property_account_receivable_id.id:
                        new_debit_account = record.env['account.account'].create({
                            'code': record.env.user.company_id.debit_account_sequence._next(),
                            'name': standard_debit_account.name,
                            'user_type_id': standard_debit_account.user_type_id.id,
                            'reconcile': True
                        })
                        partner_id.property_account_receivable_id = new_debit_account
                        record.account_id = new_debit_account

            # Account Payable
            standard_credit_account_id = partner_id.default_get(partner_id._fields).get('property_account_payable_id')
            standard_credit_account = record.env['account.account'].browse(standard_credit_account_id)

            if record.type in ['in_invoice', 'in_refund']:
                if record.env.user.company_id.create_bmd_credit_account == 'on_first_invoice' and partner_id.supplier:
                    if standard_credit_account_id == partner_id.property_account_payable_id.id:
                        new_credit_account = record.env['account.account'].create({
                            'code': record.env.user.company_id.credit_account_sequence._next(),
                            'name': standard_credit_account.name,
                            'user_type_id': standard_credit_account.user_type_id.id,
                            'reconcile': True
                        })
                        partner_id.property_account_payable_id = new_credit_account
                        record.account_id = new_credit_account
        return super(AccountInvoice, self).action_invoice_open()
