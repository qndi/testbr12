# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _


class EfrInvoiceTerm(models.Model):
    _name = 'efr.invoice.term'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'EFR Kondition'
    _order = 'name'

    name = fields.Char(string="Bezeichnung", required=True, tracking=True)
    line_ids = fields.One2many('efr.invoice.term.line', 'invoice_term_id', string="Kassa-Basisprodukte",
                               ondelete="cascade",
                               help="Diese Produkte werden pro Kasse zum Abo automatisch hinzugefügt. "
                                    "Wenn neue Kassen hinzugefügt werden, so werden diese anteilig in der "
                                    "Rechnung berücksichtigt.")
    upgrade_product_id = fields.Many2one('product.product', string="Produkt Archivupgrade", required=True,
                                         help="Dieses Produkt wird verrechnet, wenn die inkludierten Transaktionen "
                                              "überschritten werden")
    upgrade_unit_price = fields.Float(string="Preis Archivupgrade",
                                      help="Mit diesem Einzelpreis wird das Archivupgrade verrechnet")
    included_transactions = fields.Integer(string="Inkludierte Transaktionen pro Kassa",
                                           help="Inkludierte Transaktionen pro Kassa und Monat")
    type_upgrade = fields.Selection([('company', "Unternehmen"), ('cash_register', "Kassa"), ('location', "Standort")],
                                    required=True,
                                    help="Definiert die Grundlage, auf dessen Archivupgrades verrechnet werden:\n"
                                         "'Unternehmen': Berücksichtigung aller Kassen im Unternehmen\n"
                                         "'Standort': Gruppierung und Berechnung der Überschreitung pro Standort\n"
                                         "'Kassa': Berechnung pro Kassa")
    unlimited_transactions = fields.Boolean('Unbegrenzte Anzahl an Transaktionen')
