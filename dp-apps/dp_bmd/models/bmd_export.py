# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models


class BmdExport(models.Model):
    _name = 'bmd.export'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BMD Export'
    _order = 'name DESC'

    TYPE = [
        ('unexported', 'Alle noch nicht exportierten Daten'),
        ('date_range', 'Datumsbereich'),
    ]

    name = fields.Date(string="Bezeichnung (Exportdatum)", required=True)
    user_id = fields.Many2one('res.users', string='Durchgeführt von')
    type = fields.Selection(TYPE, string='Typ')
    date_begin = fields.Date(string='Datum von')
    date_end = fields.Date(string='Datum bis')
    customer_count = fields.Integer(string='# Kunden', help='Anzahl der exportierten Kunden', readonly=True)
    invoice_count = fields.Integer(string='# Rechnungen', help='Anzahl der exportierten Ausgangsrechnungen', readonly=True)

    @api.model
    def set_default_bmd_codes(self):
        bmd_code_mapper = {
            'l10n_at.1_tax_at_mwst_20': 1,
            'l10n_at.1_tax_at_mwst_10': 1,
            'l10n_at.1_tax_at_vst_20': 2,
            'l10n_at.1_tax_at_vst_10': 2,
            'l10n_at.1_tax_import_20': 9,
            'l10n_at.1_tax_import_10': 9,
            'l10n_at.1_tax_eu_20_purchase': 9,
            'l10n_at.1_tax_eu_10_purchase': 9,
            'l10n_at.1_tax_at_mwst_20_eu': 77,
            'l10n_at.1_tax_at_mwst_10_eu': 77,
            'l10n_at.1_tax_eu_sale_at': 9,
            'l10n_at.1_tax_export_at': 5,
        }
        for xml_id in bmd_code_mapper:
            if self.env.ref(xml_id, raise_if_not_found=False):
                self.env.ref(xml_id).bmd_tax_code = bmd_code_mapper[xml_id]
