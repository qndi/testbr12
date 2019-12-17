# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import base64
import binascii
import time

from odoo import models, fields, api
from odoo.exceptions import Warning
from odoo.tools import config, safe_eval
from ..e_invoice import EInvoiceService


class account_invoice(models.Model):
    _name = "account.invoice"
    _inherit = 'account.invoice'

    @api.multi
    def _is_customer_of_bund(self):
        for invoice in self:
            if invoice.partner_id and invoice.partner_id.eb_interface_para and len(invoice.partner_id.eb_interface_para) > 0:
                invoice.is_customer_of_bund = True
            else:
                invoice.is_customer_of_bund = False

    e_invoice_fields = [
        ('sent', 'Gesendet'),
        ('outstanding', u'Ausständig'),
    ]

    e_invoice = fields.Selection(e_invoice_fields, 'E-Rechnung')
    e_invoice_transmitted = fields.Boolean(string="E-Rechnung erfolgreich gesendet", readonly=True, copy=False)
    is_customer_of_bund = fields.Boolean(string="Ist Kunde von Bund", compute=_is_customer_of_bund)
    period_of_performance_from = fields.Date(string="Leistungszeitraum von", track_visibility='onchange')
    period_of_performance_to = fields.Date(string="Leistungszeitraum bis", track_visibility='onchange')

    @api.onchange('period_of_performance_from', 'period_of_performance_to')
    @api.constrains('period_of_performance_from', 'period_of_performance_to')
    def _onchange_period_from(self):
        if not self.period_of_performance_from or not self.period_of_performance_to:
            return

        if self.period_of_performance_from > self.period_of_performance_to:
            raise Warning(u"Leistungszeitraum \"von\" muss kleiner sein als Leistungszeitraum \"bis\"")

    @api.multi
    def action_invoice_open(self):
        res = super(account_invoice, self).action_invoice_open()

        if self.is_customer_of_bund:
            self.e_invoice = 'outstanding'

        return res

    @api.multi
    def action_send_e_invoice(self):
        update_context = {
            'active_id': self.id,
            'active_ids': self._ids
        }
        return {
            'name': 'E-Rechnungsversand',
            'view_type': 'form',
            'context': self.with_context(update_context).env.context,
            'view_mode': 'form',
            'res_model': 'e_invoice.wizard',
            'src_model': 'account.invoice',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def send_e_invoice(self, attachments=None):
        e_invoice_service = EInvoiceService(self.env)

        # append the attachment with the printout of the invoice if configured in the company
        if self.env.user.company_id.send_invoice:
            if not attachments:
                attachments = []

            report = self.env.ref('account.account_invoices')
            pdf = self.env['report'].get_pdf([self.id], 'account.report_invoice')
            filename = safe_eval(report.print_report_name, {'object': self, 'time': time})
            datas = base64.b64encode(pdf)

            attachments.append(
                {
                    'filename': filename,
                    'data': datas
                }
            )

        response = e_invoice_service.deliver_invoice(self, attachments)

        self.e_invoice = 'sent'
        self.e_invoice_transmitted = True

        environment = config.get('environment', 'TEST')
        post_message = 'E-Rechnung an Bund gesendet%s<br/>Antwort E-Rechnung WebService<br/>'
        post_message %= '' if environment == 'PROD' else ' (TestMode)'

        if 'DocumentID' in response:
            post_message += '&nbsp; &nbsp; &bull;&nbsp;<b>DocumentID</b>: %s<br/>' % response.DocumentID
        if 'SupplierID' in response:
            post_message += '&nbsp; &nbsp; &bull;&nbsp;<b>SupplierID</b>: %s<br/>' % response.SupplierID
        if 'SupplierEmail' in response:
            post_message += '&nbsp; &nbsp; &bull;&nbsp;<b>SupplierEmail</b>: %s<br/>' % response.SupplierEmail
        if 'SupplierInvoiceNumber' in response:
            post_message += '&nbsp; &nbsp; &bull;&nbsp;<b>SupplierInvoiceNumber</b>: %s<br/>' % response.SupplierInvoiceNumber
        if 'OrderID' in response:
            post_message += '&nbsp; &nbsp; &bull;&nbsp;<b>OrderID</b>: %s<br/>' % response.OrderID

        attachment_list = [(a['filename'], binascii.a2b_base64(a['data'])) for a in attachments or []]

        if environment != 'PROD':
            attachment_list.append(('e_rechnung.xml', base64.b64decode(e_invoice_service.get_e_invoice().value)))

        self.message_post(body=post_message, attachments=attachment_list)
