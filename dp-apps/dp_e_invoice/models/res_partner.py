# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import models, fields

EB_INTERFACE_PARAM = [('group', 'Gruppe'), ('ref', 'Bestellreferenz')]


class Partner(models.Model):
    _inherit = 'res.partner'

    eb_interface_para = fields.Selection(EB_INTERFACE_PARAM, string='EB Interface – Parameter', help='Wenn "Bestellreferenz", dann wird das Feld "Referenz/Beschreibung" übergeben')
    eb_group = fields.Many2one('eb.group', string="EB Gruppe")
    eb_bank_id = fields.Many2one(comodel_name='res.partner.bank', string='EB Bank',
                                 domain=lambda self: [('id', '=', self.env.user.company_id.bank_ids.ids)])
