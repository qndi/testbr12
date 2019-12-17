# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import uuid

from odoo import api, fields, models, _ as TRANS

class Import(models.TransientModel):
    _inherit = 'base_import.import'

    def get_guaranteed_xml_id(self, record):
        # returns the xmlid if exists, otherwise a new random XMLID is created
        self.ensure_one()

        xmlid = record.get_external_id()[record.id]
        if not xmlid:
            xmlid = '__dp__.%s_%s_%s' % (self.env[self.res_model]._table, record.id, uuid.uuid4().hex[:8])
            data = [
                {'xml_id': xmlid,
                 'record': record,
                 'noupdate': True,
                 },

            ]
            self.env['ir.model.data']._update_xmlids(data)
        return xmlid

    @api.model
    def _convert_import_data(self, fields, options):

        data, import_fields = super(Import, self)._convert_import_data(fields, options)

        if self.env.context.get('dp_config_search_fields', False):

            # Füge die Spalte für die XMLID in den Feldern hinzu
            import_fields.append('id')
            for d in data:
                domain = []
                for f in self.env.context.get('dp_config_search_fields'):

                    # Auflösen von 'payment_id/id' in ['payment_id','id']
                    fixed_fields = [models.fix_import_export_id_paths(f) for f in fields]
                    # Erstellen eines dict() pro Record mit den Fields und den Daten
                    extracted = self.env[self.res_model]._extract_records(fixed_fields, [d])
                    # Konvertieren der Daten je nach Feldtyp, zB bei many2one von XMLID auf DB-ID
                    converted = self.env[self.res_model]._convert_records(extracted)
                    # Es wird nur ein Record konvertiert
                    _, _, e_record, _ = next(converted)

                    if f not in e_record:
                        raise ValueError(TRANS("Model '%s': Feld '%s' ist nicht in den Werten") % (self.res_model, f))

                    # Adapt the search condition and use the DB-ID instead of the XMLID
                    domain.append((f, '=', e_record[f]))

                recs = self.env[self.res_model].with_context(active_test=False).search(domain)
                if len(recs) > 1:
                    # TODO Fehler wird nicht nach außen gegeben
                    raise ValueError(
                        TRANS("Model '%s': Suche mit Domain '%s' ist nicht eindeutig") % (self.res_model, domain))

                # Pro Eintrag für die XMLID als neue Spalte dazu
                if recs:
                    d.append(self.get_guaranteed_xml_id(recs[0]))
                else:
                    d.append('')

        return data, import_fields
