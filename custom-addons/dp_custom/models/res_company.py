# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

import requests
import json
import logging
from odoo import fields, models, _
from odoo.tools import config
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

API_HEADER = {'api_key': config.get('api_key', ''), "accept": "application/json",
                  "Content-Type": "application/json-patch+json"}

class ResCompany(models.Model):
    _inherit = 'res.company'

    last_partner_sync = fields.Char(string="Letzter Partner-Sync", help="Zeitpunkt des letzten Partner-Syncs", default='1990-01-01T00:00:00.00Z')
    last_cashreg_sync = fields.Char(string="Letzter Kassa-Sync", help="Zeitpunkt des letzten Kassa-Syncs", default='1990-01-01T00:00:00.00Z')
    last_trans_sync = fields.Char(string="Letzter Transaktionen-Sync", help="Zeitpunkt des letzten Transaktionen-Syncs", default="1990-01-01")
    last_location_sync = fields.Char(string="Letzter Standort-Sync", help="Zeitpunkt des letzten Standort-Syncs", default='1990-01-01T00:00:00.00Z')


    def post_response(self, path, data):
        _logger.debug(path + " Request with " + str(data))
        try:
            response = requests.post(path, headers=API_HEADER, data=json.dumps(data))
            _logger.debug("Response " + str(response.status_code) + "\n" + response.text)

            if response.ok:
                return response.json()
            response.raise_for_status()
        except Exception as e:
            _logger.debug(e)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                raise ValidationError(_('Fehler beim Zugriff auf die Schnittstelle: %s') % e.response.text)
            raise ValidationError(_('Fehler beim Zugriff auf die Schnittstelle (%s)') % e)


    # token = "abc" or token = null if last page
    def _get_items_sst(self, path, data):
        if data.get('token', False) is None:                           # if last page has been done already
            return {}

        sst_path = "%s/%s" % (config.get('sst_path', ''), path)
        response = self.env.user.company_id.post_response(sst_path, data=data)
        return response


    def _get_updated_fields(self, record, values):
        #   get dict of changed values
        result = {}
        for field in values:
            if field not in record._fields:
                continue
            if values[field] is None:
                values[field] = False
            if record._fields[field].type in ['char', 'integer', 'boolean'] and record[field] != values[field]:
                result[field] = values[field]
            elif record._fields[field].type == 'many2one' and record[field].id != values[field]:
                result[field] = values[field]
            elif record._fields[field].type == 'date' and fields.Date.to_string(record[field]) != values[field]:
                result[field] = values[field]
            elif record._fields[field].type == 'datetime' and fields.Datetime.to_string(record[field]) != values[field]:
                result[field] = values[field]
        return result
