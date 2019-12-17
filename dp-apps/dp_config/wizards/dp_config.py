# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import re
from datetime import datetime

from odoo import api, fields, models, _ as TRANS
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config


class DpConfigWizard(models.TransientModel):
    _name = 'dp.config.wizard'
    _description = 'Configuration Wizard'

    def _default_filename(self):
        d = datetime.now().strftime('%Y%m%d_%H%M')
        c = re.sub("[^a-zA-Z0-9]", "", self.env.user.company_id.name[:10])
        return '%s_%s' % (c, d)

    def _default_notes(self):
        notes = "Config 'limit_time_real' = %s\n" % config.get('limit_time_real')
        notes += "Config 'limit_time_cpu' = %s\n" % config.get('limit_time_cpu')
        notes += "Config 'limit_memory_soft' = %s\n" % config.get('limit_memory_soft')
        notes += "Config 'workers' = %s\n" % config.get('workers')
        notes += "(Die CPU Limits werden während dem Import bei Bedarf angehobgen)\n"
        return notes

    name = fields.Char('Dateiname', default=_default_filename, help='Dateiname ohne Endung ".zip"')
    zip_file = fields.Binary('Konfiguration .ZIP file')
    zip_filename = fields.Char('Dateiname ZIP')
    notes = fields.Text('Hinweise', default=_default_notes, readonly=True)
    export_products = fields.Boolean('Exportiere Produktdaten',
                                     help="Produkte, Kategorien, Preislisten, Lieferantendaten")
    export_partners = fields.Boolean('Exportiere Kontakte',
                                    help="Inkludiert Kunden, Lieferanten und sonstiges Adressen und Kontakte")
    export_from = fields.Datetime('Export ab',
                                  help='Es werden alle Datensätze mit einem neuerem Erstellungs- oder Änderungsdatum exportiert. Wenn nicht angegeben, so werden alle Datensätze exportiert')

    @api.constrains('name')
    def _check_filename(self):
        if self.name and not re.match("^[a-zA-Z0-9_-]{3,}$", self.name):
            raise ValidationError(
                TRANS("Der Dateiname muss mind. 3 Zeichen haben und darf nur folgende Zeichen enthalten: 'a-zA-Z0-9_'"))

    def do_import(self):
        self.ensure_one()

        vals = {
            'name': self.zip_filename,
            'action': 'import',
            'zip_filename': self.zip_filename,
            'zip_file': self.zip_file,
        }

        config_id = self.env['dp.config'].create(vals)
        return config_id.do_import()

    def do_export(self):
        self.ensure_one()

        vals = {
            'name': self.name,
            'action': 'export',
            'zip_filename': self.name,
            'zip_file': self.zip_file,
            'export_products': self.export_products,
            'export_partners': self.export_partners,
            'export_from': self.export_from,
        }

        config_id = self.env['dp.config'].create(vals)
        return config_id.do_export()
