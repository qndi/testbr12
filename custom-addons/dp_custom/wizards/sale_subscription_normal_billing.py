# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _


class SaleSubscriptionNormalBilling(models.TransientModel):
    _name = 'sale.subscription_normal_billing'
    _description = 'Normale Verrechnung'

    @api.multi
    def button_confirm(self):
        selected_subs = self.env['sale.subscription'].browse(self._context.get('active_ids', []))
        for sub in selected_subs:
            sub.recurring_invoice()
        invoices = self.env['account.invoice'].search(
            [('invoice_line_ids.subscription_id', 'in', self._context.get('active_ids', []))])
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        action["context"] = {"create": False}
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            action['res_id'] = invoices.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
