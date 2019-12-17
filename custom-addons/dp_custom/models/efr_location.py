# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

import logging
from odoo import api, fields, models, registry, _
from odoo.addons.queue_job.job import job, related_action
from odoo.tools import config

_logger = logging.getLogger(__name__)


class EfrLocation(models.Model):
    _name = 'efr.location'
    _description = 'EFR Standort'
    _order = "name,id"
    _inherit = ['mail.thread']

    name = fields.Char(string='Bezeichnung', required=True, track_visibility="onchange")
    portal_id = fields.Char(string="Portal ID")
    partner_id = fields.Many2one("res.partner", string="Unternehmen", required=True)

    _sql_constraints = [
        ('portal_id_uniq', 'unique (portal_id)', 'Die externe ID (portal_id) muss eindeutig sein!')
    ]

    @job(func=None, default_channel='root.sst')
    def job_sync_locations_from_efsta_cloud(self, company_id = 0):
        path = 'EfstaBilling/Locations'
        data = {'limit': 10, 'companyId': company_id, 'lastSyncDate': self.env.user.company_id.last_location_sync}
        if company_id:
            data['lastSyncDate'] = "1990-01-01T00:00:00.00Z"

        response = self.env['res.company']._get_items_sst(path=path, data=data)
        while response.get('list', False):
            locationIds = response['list']
            data['token'] = response['token']
            response = self.env['res.company']._get_items_sst(path=path, data=data)

            for record in locationIds:
                # Update latest Sync Date
                if record.get('dateLastChanged', False) and record['dateLastChanged'] > data['lastSyncDate']:
                        data['lastSyncDate'] = record['dateLastChanged']

                if not self.env['res.partner']._get_api_partner(record['companyId']):
                    self.env['res.partner'].update_partner_efsta_cloud([record['companyId']])

                vals = self._prepare_sst_values(record)

                location = self.env['efr.location'].search([('portal_id', '=', vals['portal_id'])])
                if location:
                    # update changed values only
                    temp_vals = self.env['res.company']._get_updated_fields(location, vals)
                    if temp_vals:
                        _logger.debug("efr.location mit id: " + str(location.id) + " write: " + str(temp_vals))
                        location.write(temp_vals)
                else:
                    _logger.debug("efr.location create: " + str(vals))
                    self.env['efr.location'].create(vals)

            if not company_id:
                if self.env.user.company_id.last_location_sync < data['lastSyncDate']:
                    self.env.user.company_id.sudo().write({'last_location_sync': data['lastSyncDate']})
                self._cr.commit()

    @api.model
    def cron_sync_from_efsta_cloud(self):
        running_jobs = self.env['queue.job'].sudo().search([('state', '!=', 'done'),
                                                            ('name', 'ilike', 'job_sync_locations_from_efsta_cloud')])
        if running_jobs:
            return

        self.env['efr.location'].with_delay().job_sync_locations_from_efsta_cloud()

    @api.multi
    def _prepare_sst_values(self, response_item):
        values = {
            'partner_id': self.env['res.partner']._get_api_partner(response_item.get('companyId', False)).id,
            'name': response_item['name'],
            'portal_id':  str(response_item['locationId']) if response_item['locationId'] is not None else False,
            }
        return values
