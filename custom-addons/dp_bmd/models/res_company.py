# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    debit_account_sequence = fields.Many2one('ir.sequence', 'Debitorenkonto Sequenz')
    create_bmd_debit_account = fields.Selection([('never', 'Nie'), ('on_first_invoice', 'Bei erster Rechnung')],
                                                'BMD: Debitorenkonto erstellen', default='never')
    credit_account_sequence = fields.Many2one('ir.sequence', 'Kreditorenkonto Sequenz')
    create_bmd_credit_account = fields.Selection([('never', 'Nie'), ('on_first_invoice', 'Bei erster Rechnung')],
                                                 'BMD: Kreditorenkonto erstellen', default='never')
