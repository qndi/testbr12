# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

import logging
from odoo import api, fields, models, registry, _
from odoo.addons.queue_job.job import job, related_action
from odoo.tools import config

_logger = logging.getLogger(__name__)


class EfrTransactions(models.Model):
    _name = 'efr.transactions'
    _description = 'EFR Transaktionen'
    _order = "period desc"
    _rec_name = "cash_register_id"

    partner_id = fields.Many2one("res.partner", string="Unternehmen", required=True)
    cash_register_id = fields.Many2one("efr.cash_register", string="Kassa", required=True)
    period = fields.Date(string="Periode", required=True, help="Ist immer der 1. des Monats")
    qty = fields.Integer(string="Anzahl Transaktionen", help="Anzahl der Transaktionen der Kassa in der Periode")
    location_id = fields.Many2one(related="cash_register_id.location_id", store=True)

    _sql_constraints = [
        ('cash_register_id_uniq', 'unique (cash_register_id, period)', 'Die Periode muss pro Kassa eindeutig sein')
    ]

    @job(func=None, default_channel='root.sst')
    def job_sync_transactions_from_efsta_cloud(self, company_id=0):
        path = 'EfstaBilling/Transactions'
        data = {'limit': 10, 'companyId': company_id, 'dateFrom': self.env.user.company_id.last_trans_sync}
        if company_id:
            data['dateFrom'] = "1990-01-01"

        response = self.env['res.company']._get_items_sst(path=path, data=data)
        while response.get('list', False):
            transactionIds = response['list']
            data['token'] = response['token']
            response = self.env['res.company']._get_items_sst(path=path, data=data)

            for record in transactionIds:
                # Update latest Sync Date
                if record.get('period', False) and record['period'] > data['dateFrom']:
                    data['dateFrom'] = record['period']

                vals = self._prepare_sst_values(record)
                transaction = self.env['efr.transactions'].search([('cash_register_id', '=', vals['cash_register_id']), ('period', '=', record['period'])])

                if transaction:
                    # update changed values only
                    temp_vals = self.env['res.company']._get_updated_fields(transaction, vals)
                    if temp_vals:
                        _logger.debug("efr.transaction mit id: " + str(transaction.id) + " write: " + str(temp_vals))
                        transaction.write(temp_vals)
                else:
                    _logger.debug("efr.transaction create: " + str(vals))
                    self.env['efr.transactions'].create(vals)

            if not company_id:
                if self.env.user.company_id.last_trans_sync < data['dateFrom']:
                    self.env.user.company_id.sudo().write({'last_trans_sync': data['dateFrom']})
                self.env.cr.commit()


    @api.model
    def cron_sync_from_efsta_cloud(self):
        running_jobs = self.env['queue.job'].sudo().search([('state', '!=', 'done'),
                                                            ('name', 'ilike', 'job_sync_transactions_from_efsta_cloud')])
        if running_jobs:
            return

        self.env['efr.transactions'].with_delay().job_sync_transactions_from_efsta_cloud()

    @api.multi
    def _prepare_sst_values(self, item):
        partner = self.env['res.partner']._get_api_partner(item['companyId'])
        if not partner:
            self.env['res.partner'].update_partner_efsta_cloud([item['companyId']])
            partner = self.env['res.partner']._get_api_partner(item['companyId'])

        values = {
            'partner_id': partner.id,
            'cash_register_id': self.env['efr.cash_register'].search([('portal_id', '=', item['cashRegId']), ('partner_id', '=', partner.id)]).id,
            'period': item['period'],
            'qty': item['transactions'],
        }

        if not values['cash_register_id']:
            # Create Cash Register if it does not exist yet
            self.env['efr.cash_register'].job_sync_cashreg_from_efsta_cloud(item['companyId'])
            values['cash_register_id'] = self.env['efr.cash_register'].search([('portal_id', '=', item['cashRegId']), ('partner_id', '=', partner.id)]).id

        return values
