# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

import stdnum.eu.vat
from zeep import Client
import json
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    vat_check_error = fields.Boolean(string="UID-Prüfung fehlgeschlagen", compute="_compute_vat_check_error",
                                     store=True, readonly=True,
                                     help="Wenn gesetzt, dann gab es hier einen Fehler bei der UID-Prüfung.")
    vat_error_msg = fields.Text(string="UID-Fehler", readonly=True)
    vat_fon_result = fields.Text(string="FON Info", readonly=True, help='Rückgabewert des FON-Services')

    @api.depends('vat_error_msg')
    def _compute_vat_check_error(self):
        for rec in self:
            if rec.vat_error_msg is not False and rec.vat_error_msg != "":
                rec.vat_check_error = True
            else:
                rec.vat_check_error = False

    @api.model
    def create(self, values):
        res = super(ResPartner, self).create(values)
        if 'vat' in values and values.get('vat') is not False:
            res.button_check_vat()
        return res

    @api.multi
    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if 'vat' in vals and vals.get('vat') is not False:
            self.button_check_vat()
        return res

    def _call_fon_webservice(self, vat):
        client = Client('https://finanzonline.bmf.gv.at/fonws/ws/sessionService.wsdl')

        # Hole Account-Daten aus Systemparametern
        tid = self.env['ir.config_parameter'].get_param('vat_check.fon_tid', 'none')
        benid = self.env['ir.config_parameter'].get_param('vat_check.fon_benid', 'none')
        pin = self.env['ir.config_parameter'].get_param('vat_check.fon_pin', 'none')
        herstellerid = self.env.user.company_id.vat

        _logger.debug("Webservice Login call")
        result = client.service.login(tid, benid, pin, herstellerid)
        _logger.debug("Webservice Login result: %s" % result)
        session_id = result.id

        client = Client('https://finanzonline.bmf.gv.at/fon/ws/uidAbfrage.wsdl')

        _logger.debug("Webservice VAT-Check call")
        uid_tn = self.env.user.company_id.vat
        stufe = 2 # Stufe 2 Abfrage: inkludiert Adressdaten
        result = client.service.uidAbfrage(tid, benid, session_id, uid_tn, vat, stufe)
        _logger.debug("Webservice VAT-Check result: %s" % result)

        # Return zeep response object
        return result

    def _parse_address(self, vat, vat_data):

        func_name = "_parse_address_%s" % vat[:2]
        method = getattr(self, func_name)
        if method:
            return method(vat_data)
        else:
            _logger.error("Method '%s' is not implemented yet" % func_name)
            return False, False, False

    def _parse_address_AT(self, vat_data):
        """
        Beispiel-Response:
            {
                'rc': 0,
                'msg': None,
                'name': 'efsta IT Services GmbH',
                'adrz1': 'Im Stadtgut A1',
                'adrz2': 'AT-4407 Steyr',
                'adrz3': None,
                'adrz4': None,
                'adrz5': None,
                'adrz6': None
            }
        """
        street = vat_data.adrz1 or False
        tmp = vat_data.adrz2.split(' ')
        if len(tmp) == 2:
            city = tmp[1]
            zip = tmp[0].split('-')[-1]
        else:
            city = False
            zip = False
        return street, zip, city

    def _parse_address_DE(self, vat_data):
        """
        Beispiel-Response:
            {
            'rc': 0,
            'msg': None,
            'name': 'Hiltes Software GmbH             ',
            'adrz1': 'Konrad-Zuse-Str. 1',
            'adrz2': None,
            'adrz3': '26789',
            'adrz4': 'Leer',
            'adrz5': None,
            'adrz6': None
        }
        """
        street = vat_data.adrz1 or False
        city = vat_data.adrz4 or False
        zip = vat_data.adrz3 or False
        return street, zip, city

    def _parse_address_IT(self, vat_data):
        """
        Beispiel-Response:
            {
                'rc': 0,
                'msg': None,
                'name': 'CONSULT SERVICE DI PIERATTINI VITTORIO E C. S.A.S.',
                'adrz1': 'VIA FILUGELLI N. 23 ',
                'adrz2': '59100 PRATO PO',
                'adrz3': None,
                'adrz4': None,
                'adrz5': None,
                'adrz6': None
            }
        """
        street = vat_data.adrz1 or False
        tmp = vat_data.adrz2.split(' ', 1)
        if len(tmp) == 2:
            city = tmp[1]
            zip = tmp[0].split('-')[-1]
        else:
            city = False
            zip = False
        return street, zip, city

    def _parse_address_HR(self, vat_data):
        """
        Beispiel-Response:
            {
                'rc': 0,
                'msg': None,
                'name': 'PALMERS D.O.O.',
                'adrz1': 'RADNIČKA CESTA 32, ZAGREB, 10000 ZAGREB',
                'adrz2': None,
                'adrz3': None,
                'adrz4': None,
                'adrz5': None,
                'adrz6': None
            }
        """
        tmp = vat_data.adrz1.split(',')
        street = ','.join(tmp[:-1])
        zip, city = tmp[-1].strip().split(' ',1)
        return street, zip, city

    def _parse_address_SI(self, vat_data):
        """
        Beispiel-Response:
            {
                'rc': 0,
                'msg': None,
                'name': 'RCL INT.D.O.O.',
                'adrz1': 'ULICA ALME SODNIK 2, 1000 LJUBLJANA',
                'adrz2': None,
                'adrz3': None,
                'adrz4': None,
                'adrz5': None,
                'adrz6': None
            }
        """
        tmp = vat_data.adrz1.split(',')
        street = ','.join(tmp[:-1])
        zip, city = tmp[-1].strip().split(' ',1)
        return street, zip, city

    def _parse_address_HU(self, vat_data):
        """
        Beispiel-Response:
            {
                'rc': 0,
                'msg': None,
                'name': 'LAUREL SZÁMITÁSTECHNIKAI KFT',
                'adrz1': '8000 SZÉKESFEHÉRVÁR GYUMOLCS U 4-6',
                'adrz2': None,
                'adrz3': None,
                'adrz4': None,
                'adrz5': None,
                'adrz6': None
            }
        """
        tmp = vat_data.adrz1.split(' ', 2)
        zip = tmp[0]
        city = tmp[1]
        street = tmp[2]
        return street, zip, city

    def _parse_address_CZ(self, vat_data):
        """
        Beispiel-Response:
            {
                'rc': 0,
                'msg': None,
                'name': 'adidas ČR s.r.o.',
                'adrz1': 'Pekařská 641/16',
                'adrz2': 'PRAHA 5 - JINONICE',
                'adrz3': '155 00  PRAHA 515',
                'adrz4': None,
                'adrz5': None,
                'adrz6': None
            }
        """
        street = vat_data.adrz1
        zip_city = vat_data.adrz3 and vat_data.adrz3 or vat_data.adrz2
        tmp = zip_city.split('  ')
        if len(tmp) == 2:
            zip = tmp[0]
            city = tmp[1]
        else:
            zip = False
            city = False
        return street, zip, city

    def _parse_address_GB(self, vat_data):
        """
        Beispiel-Response:
            {
                'rc': 0,
                'msg': None,
                'name': 'APTOS SOLUTIONS UK LIMITED',
                'adrz1': '3RD FLOOR',
                'adrz2': 'MARLOW INTERNATIONAL',
                'adrz3': 'MARLOW',
                'adrz4': 'BUCKINGHAMSHIRE',
                'adrz5': None,
                'adrz6': 'SL7 1YL'
            }
        """
        zip = vat_data.adrz6 or False
        city = vat_data.adrz4 or False
        street = vat_data.adrz1 + ', ' + vat_data.adrz2 + ', ' + vat_data.adrz3

        return street, zip, city

    def _parse_address_FR(self, vat_data):
        """
        Beispiel-Response:
            {
                'rc': 0,
                'msg': None,
                'name': 'SASU SARL BLACLAND',
                'adrz1': 'CTRE COMMERCIAL BLAGNAC',
                'adrz2': '2 ALL EMILE ZOLA',
                'adrz3': '31700 BLAGNAC',
                'adrz4': None,
                'adrz5': None,
                'adrz6': None
            }
        """
        if vat_data.adrz3: # Annahme, dass es hier 3 Adresszeilen gibt
            street = vat_data.adrz2 or False
            tmp = vat_data.adrz3 and vat_data.adrz3.split(' ', 1) or []
            if len(tmp) == 2:
                city = tmp[1]
                zip = tmp[0]
            else:
                city = False
                zip = False
            return street, zip, city
        else:
            # 2 Adresszeilen
            street = vat_data.adrz1 or False
            tmp = vat_data.adrz2 and vat_data.adrz2.split(' ') or []
            if len(tmp) == 2:
                city = tmp[1]
                zip = tmp[0]
            else:
                city = False
                zip = False
            return street, zip, city

    def button_check_vat(self):
        for rec in self:
            if not rec.vat:
                continue

            try:
                #result = stdnum.eu.vat.check_vies(rec.vat)
                vat_data = rec._call_fon_webservice(rec.vat)
                rec.vat_error_msg = ""
                if vat_data.rc != 0:
                    rec.vat_error_msg = vat_data.msg
                else:
                    rec.vat_fon_result = vat_data
                    street, zip, city = rec._parse_address(rec.vat, vat_data)
                    if rec.name != vat_data.name:
                        rec.vat_error_msg += "Fehler in UID-Prüfung: Feld 'Name' stimmt nicht überein: Odoo: " + \
                                             rec.name + ", VIES: " + vat_data.name + "\n"
                    if rec.street != street:
                        rec.vat_error_msg += "Fehler in UID-Prüfung: Feld 'Straße' stimmt nicht überein: Odoo: " + \
                                             (str(rec.street) if rec.street else '<Leer>') + ", VIES: " + street + "\n"
                    if rec.zip != zip:
                        rec.vat_error_msg += "Fehler in UID-Prüfung: Feld 'PLZ' stimmt nicht überein: Odoo: " + \
                                             (str(rec.zip) if rec.zip else '<Leer>') + ", VIES: " + zip + "\n"
                    if rec.city != city:
                        rec.vat_error_msg += "Fehler in UID-Prüfung: Feld 'Stadt' stimmt nicht überein: Odoo: " + \
                                             (str(rec.city) if rec.city else '<Leer>') + ", VIES: " + city + "\n"
            except:
                rec.vat_error_msg = "Unbekannter Fehler in der UID-Prüfung"
