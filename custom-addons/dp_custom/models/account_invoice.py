# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    subscription_partner_id = fields.Many2one('res.partner', string="Abo-Partner",
                                              help="Wird für die Kennzeichnung der Rechnung benötigt, wenn im "
                                                   "Vertriebspartner das Flag 'Rechnung pro Unternehmen' gesetzt ist")
    subscription_template_id = fields.Many2one('sale.subscription.template', string="Abo-Vorlage")
    subscription_invoice_date = fields.Date("Abo-Abrechnungsdatum")
    is_subsequent = fields.Boolean(string="Ist Nachverrechnung", help="Ist gesetzt, wenn es sich um eine "
                                                                      "Nachverrechnung von Transaktionsüberschreitungen "
                                                                      "handelt.")
