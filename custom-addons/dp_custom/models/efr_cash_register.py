# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

import logging
from odoo import api, fields, models, registry, _
from odoo.addons.queue_job.job import job, related_action
from odoo.tools import config

_logger = logging.getLogger(__name__)


class EfrCashRegister(models.Model):
    _name = 'efr.cash_register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'EFR Kassa'
    _order = "partner_id, location_id, date_start DESC"
    _rec_name = 'portal_id'

    partner_id = fields.Many2one("res.partner", string="Unternehmen", required=True)
    portal_id = fields.Char(string="Portal ID", required=True)
    date_start = fields.Date(string="Startdatum", track_visibility="onchange", required=True)
    date_end = fields.Date(string="Enddatum", track_visibility="onchange")
    date_last_transaction = fields.Date(string="Letzte Transaktion")
    location_id = fields.Many2one("efr.location", string="Standort", track_visibility="onchange",
                                  help="Standort, dem die Kassa zugeordnet ist. Wird im Portal zugewiesen.")
    efr_registers = fields.Char(string="EFR-Register", track_visibility="onchange", help="Kommagetrennte Liste von EFR-Registern")


    _sql_constraints = [
        ('portal_id_partner_id_uniq', 'unique (portal_id, partner_id)', 'Die externe ID (portal_id) muss pro Unternehmen eindeutig sein!')
    ]

    @job(func=None, default_channel='root.sst')
    def job_sync_cashreg_from_efsta_cloud(self, company_id = 0):
        path = 'EfstaBilling/POSList'
        data = {'limit': 10, 'companyId': company_id, 'lastSyncDate': self.env.user.company_id.last_cashreg_sync}
        if company_id:
            data['lastSyncDate'] = "1990-01-01T00:00:00.00Z"
            data['companyId'] = company_id

        response = self.env['res.company']._get_items_sst(path=path, data=data)
        while response.get('list', False):
            cashRegIds = response['list']
            data['token'] = response['token']
            response = self.env['res.company']._get_items_sst(path=path, data=data)

            for record in cashRegIds:
                # Update latest Sync Date
                if record.get('dateLastChanged', False) and record['dateLastChanged'] > data['lastSyncDate']:
                    data['lastSyncDate'] = record['dateLastChanged']

                if not self.env['res.partner']._get_api_partner(record['companyId']):
                    self.env['res.partner'].update_partner_efsta_cloud([record['companyId']])

                if record.get('locationId', False) and not self.env['efr.location'].search([('portal_id', '=', record['locationId'])]):
                        self.env['efr.location'].job_sync_locations_from_efsta_cloud(company_id=record['companyId'])

                vals = self._prepare_sst_values(record)

                cashReg = self.env['efr.cash_register'].search([('portal_id', '=', vals['portal_id']), ('partner_id', '=', vals['partner_id'])])
                if cashReg:
                    # update changed values only
                    temp_vals = self.env['res.company']._get_updated_fields(cashReg, vals)
                    if temp_vals:
                        _logger.debug("efr.cash_register mit id: " + str(cashReg.id) + " write: " + str(temp_vals))
                        cashReg.write(temp_vals)
                else:
                    _logger.debug("efr.cash_register create: " + str(vals))
                    self.env['efr.cash_register'].create(vals)

            if not company_id:
                if self.env.user.company_id.last_cashreg_sync < data['lastSyncDate']:
                    self.env.user.company_id.sudo().write({'last_cashreg_sync': data['lastSyncDate']})
                self.env.cr.commit()

    @api.model
    def cron_sync_from_efsta_cloud(self):
        running_jobs = self.env['queue.job'].sudo().search([('state', '!=', 'done'),
                                                            ('name', 'ilike', 'job_sync_cashreg_from_efsta_cloud')])
        if running_jobs:
            return

        self.env['efr.cash_register'].with_delay().job_sync_cashreg_from_efsta_cloud()

    @api.multi
    def _prepare_sst_values(self, response_item):
        partner = self.env['res.partner']._get_api_partner(response_item['companyId'])
        values = {
            'partner_id': partner.id,
            'portal_id': response_item['cashRegId'],
            'efr_registers': response_item['registerNr'],
            'date_start': response_item['startDate'],
            'date_end': response_item['endDate'],
            'date_last_transaction': response_item['dateLastTransaction'],
            'location_id': self.env['efr.location'].search([('portal_id', '=', response_item.get('locationId', False)),('partner_id','=',partner.id)]).id,
            }
        return values

    @api.multi
    def show_transactions(self):
        action_view = self.env.ref('dp_custom.efr_transactions_action').read()[0]
        domain = [('cash_register_id', '=', self.id)]
        transactions = self.env['efr.transactions'].search(domain)

        action_view['view_mode'] = 'tree,form'
        action_view['views'] = [(False, u'tree'), (False, u'form')]
        action_view['domain'] = "[('id', 'in', %s)]" % (transactions.ids,)
        action_view['context'] = '{}'
        return action_view
