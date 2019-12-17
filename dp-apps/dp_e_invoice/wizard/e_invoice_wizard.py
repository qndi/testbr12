# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models


class e_invoice_wizard(models.TransientModel):
    _name = 'e_invoice.wizard'

    document_1 = fields.Binary(string='Dokument 1')
    document_2 = fields.Binary(string='Dokument 2')
    document_3 = fields.Binary(string='Dokument 3')
    document_4 = fields.Binary(string='Dokument 4')
    document_5 = fields.Binary(string='Dokument 5')

    filename_document_1 = fields.Char(string='Filename 1')
    filename_document_2 = fields.Char(string='Filename 2')
    filename_document_3 = fields.Char(string='Filename 3')
    filename_document_4 = fields.Char(string='Filename 4')
    filename_document_5 = fields.Char(string='Filename 5')

    @api.multi
    def send_e_invoice(self):
        active_ids = self._context.get('active_ids', [])
        if len(active_ids) > 1:
            raise Warning("E-Rechnungsversand kann jeweils nur für 1 Rechnung erfolgen")
        if len(active_ids) == 0:
            raise Warning("Rechnung nicht vorhanden")

        attachments = []

        if self.document_1:
            attachments.append(
                {
                    'filename': self.filename_document_1,
                    'data': self.document_1
                }
            )
        if self.document_2:
            attachments.append(
                {
                    'filename': self.filename_document_2,
                    'data': self.document_2
                }
            )
        if self.document_3:
            attachments.append(
                {
                    'filename': self.filename_document_3,
                    'data': self.document_3
                }
            )
        if self.document_4:
            attachments.append(
                {
                    'filename': self.filename_document_4,
                    'data': self.document_4
                }
            )
        if self.document_5:
            attachments.append(
                {
                    'filename': self.filename_document_5,
                    'data': self.document_5
                }
            )

        invoice = self.env['account.invoice'].browse(active_ids[0])
        invoice.send_e_invoice(attachments)

        return {
            'type': 'ir_actions_act_close_wizard_and_send_notification',
            'title': u'E-Rechnung erfolgreich versendet',
            'message': u'Webservice Rückmeldung wurde im Chatter protokolliert'
        }
