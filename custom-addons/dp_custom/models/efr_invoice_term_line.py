# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _


class EfrInvoiceTermLine(models.Model):
    _name = 'efr.invoice.term.line'
    _description = 'EFR Konditionsposition'
    _order = 'invoice_term_id'

    invoice_term_id = fields.Many2one('efr.invoice.term', string="Kondition", required=True)
    product_id = fields.Many2one('product.product', string="Produkt", required=True)
    price_unit = fields.Float(string="Einzelpreis")
