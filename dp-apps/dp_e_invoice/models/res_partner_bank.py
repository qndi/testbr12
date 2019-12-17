# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import models, fields


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    bank_for_eb = fields.Boolean(string=u"Bank für EB", help=u"Bank für E-Rechnung")
    bank_id = fields.Many2one(required=True)

class ResBank(models.Model):
    _inherit = "res.bank"

    bic = fields.Char(required=True)



