# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

import logging
from odoo import api, fields, models, registry, _
from odoo.addons.queue_job.job import job, related_action
from odoo.tools import config, relativedelta
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

sst_keys = [
    "eci",
    "ecit",
    "name",
    "street",
    "city",
    "zip",
    "country_id",
    "email",
    "active",
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_reseller = fields.Boolean(string="Ist ein Vertriebspartner",
                                 help="Kennzeichen, ob es sich bei dem Partner um einen Vertriebspartner handelt")
    reseller_partner_id = fields.Many2one("res.partner", string="Vertriebspartner", domain=[("is_reseller", "=", True)],
                                          help="Kennzeichnet den Vertriebspartner zu diesem Unternehmen")
    ecit = fields.Char(string="ECIT", help="Steuertyp, EU01 - UID, AT01 - Steuernummer, GLN - Global Location Nr.")
    eci = fields.Char(string="ECI", help="UID-Nummer, Steuernummer oder GLN (je nach ECIT)")
    manual_invoice_partner_id = fields.Many2one('res.partner', string="Verrechnungspartner",
                                                help="Wenn nicht befüllt, dann ist die Rechnungsadresse der eigene Partner",
                                                track_visibility='onchange')
    invoice_partner_id = fields.Many2one('res.partner', string="Verrechnungspartner computed", readonly=True,
                                         compute="_compute_invoice_partner_id", store=True)
    cash_register_ids = fields.One2many('efr.cash_register', 'partner_id', string="Kassen")
    portal_id = fields.Char(string="Portal ID")
    single_invoice = fields.Boolean(string='Rechnung pro Unternehmen',
                                    help='Wenn gesetzt, dann wird für alle Abos, die diesen Partner als '
                                         'Verrechnungspartner gesetzt haben, eine eigene Rechnung erzeugt. '
                                         'Als Rechnungsempfänger bleibt der Verrechnungspartner.',
                                    default=False)
    cash_register_count = fields.Integer(compute='_compute_cash_register_count', string="Anzahl Kassen")
    location_count = fields.Integer(compute='_compute_location_count', string="Anzahl Standorte")
    efr_invoice_term_id = fields.Many2one('efr.invoice.term', string="Konditionen", tracking=True)
    subscription_template_id = fields.Many2one('sale.subscription.template', string='Abo-Vorlage',
                                               track_visibility='onchange')
    has_active_cash_register = fields.Boolean(string="Partner hat aktive Kasse ohne Abo",
                                              compute="_compute_has_active_cash_register", readonly=True)

    _sql_constraints = [
        ('portal_id_uniq', 'unique (portal_id)', 'Die externe ID (portal_id) muss eindeutig sein!')
    ]

    def _compute_has_active_cash_register(self):
        for rec in self:
            if rec.cash_register_ids.filtered(lambda x: x.date_start <= fields.date.today() and
                                                        (x.date_end == False or x.date_end >= fields.date.today())) and \
                    not rec.env['sale.subscription'].search([('partner_id', '=', rec.id),
                                                             ('in_progress', '=', True)]):
                rec.has_active_cash_register = True
            else:
                rec.has_active_cash_register = False

    @api.multi
    def button_sync_cashreg(self):
        self.ensure_one()
        if not self.portal_id:
            raise ValidationError('Dieser Kunde wurde noch nicht mit dem Kassensystem synchronisiert!')
        _logger.debug("Button Sync Cashreg, res.partner " + str(self.id))
        self.env['efr.cash_register'].job_sync_cashreg_from_efsta_cloud(company_id=self.portal_id)

    @api.multi
    def button_sync_transactions(self):
        self.ensure_one()
        if not self.portal_id:
            raise ValidationError('Dieser Kunde wurde noch nicht mit dem Kassensystem synchronisiert!')
        _logger.debug("Button Sync Transactions, res.partner " + str(self.id))
        self.env['efr.transactions'].job_sync_transactions_from_efsta_cloud(company_id=self.portal_id)

    @api.multi
    def button_sync_sst_partner(self):
        self.ensure_one()
        if not self.portal_id:
            raise ValidationError('Dieser Kunde wurde noch nicht mit dem Kassensystem synchronisiert!')
        _logger.debug("Button Sync Company, res.partner: " + str(self.id))
        self.env['efr.location'].job_sync_locations_from_efsta_cloud(company_id=self.portal_id)
        self.update_partner_efsta_cloud(company_list=[self.portal_id])

    def update_partner_efsta_cloud(self, company_list):
        sst2_path = "%s/%s" % (config.get('sst_path', ''), 'EfstaBilling/CompanyDetails')
        sst2_response = self.env.user.company_id.post_response(sst2_path, data=company_list)
        last_sync_date = "1990-01-01T00:00:00.00Z"
        if self.env.context.get('sync_date', False):
            last_sync_date = self.env.user.company_id.last_partner_sync

        for record in sst2_response:
            # Update latest Sync Date
            if record.get('dateLastChanged', False) and record['dateLastChanged'] > last_sync_date:
                last_sync_date = record['dateLastChanged']

            if 'companyType' in record and record['companyType'] in ['O', 'C']:
                partner = self._get_api_partner(record['companyId'])

                #   Create referenced companies, if they don't exist yet
                for partnerType in ["invoiceCompanyId", "partnerCompanyId"]:
                    if record.get(partnerType, False) and record[partnerType] != record['companyId']:
                        if not self._get_api_partner(record[partnerType]):
                            # create related partner if it does not exist
                            temp_response = self.env.user.company_id.post_response(sst2_path,
                                                                                   data=[record[partnerType]])
                            temp_vals = self._prepare_sst_values(temp_response[0])
                            del temp_vals['manual_invoice_partner_id']
                            del temp_vals['reseller_partner_id']
                            self.env['res.partner'].create(temp_vals)

                vals = self._prepare_sst_values(record)
                if partner:
                    # update changed values only
                    temp_vals = self.env['res.company']._get_updated_fields(partner, vals)
                    if temp_vals:
                        _logger.debug("res.partner mit id: " + str(partner.id) + " write: " + str(temp_vals))
                        partner.with_context(sst=True).write(temp_vals)
                else:
                    _logger.debug("res.partner create: " + str(vals))
                    partner.create(vals)

        # Sync Date only if called by Cronjob
        if self.env.context.get('sync_date', False):
            if self.env.user.company_id.last_partner_sync < last_sync_date:
                self.env.user.company_id.sudo().write({'last_partner_sync': last_sync_date})
            self._cr.commit()

    @job(func=None, default_channel='root.sst')
    @related_action('related_action_open_record')
    def job_sync_partner_from_efsta_cloud(self):
        last_sync = self.env.user.company_id.last_partner_sync
        data = {'limit': 10, 'lastSyncDate': last_sync}
        sst1_response = self.env['res.company']._get_items_sst(path='EfstaBilling/CompanyChanges', data=data)
        context = dict(self.env.context, sync_date=True)
        while sst1_response.get('companyIdList', False):
            companyIdList = sst1_response['companyIdList']
            self.env['res.partner'].with_context(context).update_partner_efsta_cloud(companyIdList)

            data = {'limit': 10, 'token': sst1_response['token']}
            sst1_response = self.env['res.company']._get_items_sst(path='EfstaBilling/CompanyChanges', data=data)
            self._cr.commit()

    @api.model
    def cron_sync_from_efsta_cloud(self):
        running_jobs = self.env['queue.job'].sudo().search([
            ('name', 'ilike', 'job_sync_partner_from_efsta_cloud'),
            ('state', '!=', 'done')])
        if running_jobs:
            return

        self.env['res.partner'].with_delay().job_sync_partner_from_efsta_cloud()

    @api.depends('manual_invoice_partner_id')
    def _compute_invoice_partner_id(self):
        for record in self:
            if record.manual_invoice_partner_id:
                record.invoice_partner_id = record.manual_invoice_partner_id
            else:
                record.invoice_partner_id = record

    @api.multi
    def _get_api_partner(self, portal_id):
        return self.env['res.partner'].with_context(active_test=False).search([('portal_id', '=', portal_id)])

    @api.multi
    def _prepare_sst_values(self, response_item):
        values = {
            'portal_id': str(response_item['companyId']) if response_item['companyId'] is not None else False,
            'active': not response_item['inactive'],
            'name': response_item['name'],
            'street': response_item['address'],
            'zip': response_item['zip'],
            'city': response_item['city'],
            'country_id': self.env['res.country'].search([('code', '=', response_item['countryCode'])]).id,
            'email': response_item['emailAddress'],
            'vat': response_item['vat'],
            'ecit': response_item['ecit'],
            'eci': response_item['eci'],
            'single_invoice': response_item['singleInvoice'],
            'manual_invoice_partner_id': self._get_api_partner(response_item.get('partnerCompanyId', False)).id,
            'reseller_partner_id': self._get_api_partner(response_item.get('partnerCompanyId', False)).id,
            'is_company': True,
            'is_reseller': True if response_item['companyType'] == "O" else False
        }
        return values

    def _prepare_odoo_values_for_sst(self):
        data = {
            "name": self.name or None,
            "address": self.street or None,
            "zip": self.zip or None,
            "city": self.city or None,
            "countryCode": self.country_id.code or None,
            "emailAddress": self.email or None,
            "eci": self.eci or None,
            "ecit": self.ecit or None,
            "inactive": not self.active
        }
        return data

    @api.multi
    def show_cash_register(self):
        action_view = self.env.ref('dp_custom.efr_cash_register_action').read()[0]
        domain = [('partner_id', '=', self.id)]
        cash_reg = self.env['efr.cash_register'].search(domain)

        action_view['view_mode'] = 'tree,form'
        action_view['views'] = [(False, u'tree'), (False, u'form')]
        action_view['domain'] = "[('id', 'in', %s)]" % (cash_reg.ids,)
        action_view['context'] = '{}'
        return action_view

    @api.multi
    def _compute_cash_register_count(self):
        for partner in self:
            partner.cash_register_count = self.env['efr.cash_register'].search_count([('partner_id', '=', partner.id)])

    @api.multi
    def show_locations(self):
        action_view = self.env.ref('dp_custom.efr_location_action').read()[0]
        domain = [('partner_id', '=', self.id)]
        location = self.env['efr.location'].search(domain)

        action_view['view_mode'] = 'tree,form'
        action_view['views'] = [(False, u'tree'), (False, u'form')]
        action_view['domain'] = "[('id', 'in', %s)]" % (location.ids,)
        action_view['context'] = '{}'
        return action_view

    @api.multi
    def _compute_location_count(self):
        for partner in self:
            partner.location_count = self.env['efr.location'].search_count([('partner_id', '=', partner.id)])

    @api.multi
    def sst_create_partner(self):
        self.ensure_one()
        if self.portal_id:
            raise ValidationError(_(u"Partner besitzt bereits eine Portal ID."))

        data = {
            "name": self.name or None,
            "address": self.street or None,
            "zip": self.zip or None,
            "city": self.city or None,
            "countryCode": self.country_id.code or None,
            "emailAddress": self.email or None,
            "eci": self.eci or None,
            "ecit": self.ecit or None,
            "inactive": not self.active
        }

        path = "%s/%s" % (config.get('sst_path', ''), 'EfstaBilling/ChangeCompany')
        response = self.env.user.company_id.post_response(path, data=data)
        self.write({'portal_id': response})

    @job(func=None, default_channel='root.sst')
    @related_action('related_action_open_record')
    def job_update_partner_on_efsta_cloud(self):
        data = self._prepare_odoo_values_for_sst()
        data["companyId"] = self.portal_id
        path = "%s/%s" % (config.get('sst_path', ''), 'EfstaBilling/ChangeCompany')
        self.env.user.company_id.post_response(path, data=data)

    @api.multi
    def write(self, vals):
        super(ResPartner, self).write(vals)
        if self.env.context.get('sst'):
            return
        for record in self:
            if record.portal_id and set(vals).intersection(set(sst_keys)):
                record.with_delay().job_update_partner_on_efsta_cloud()

    @api.model
    def create(self, vals):
        res = super(ResPartner, self).create(vals)
        if res.reseller_partner_id:
            # Wenn Vertriebspartner beim Erstellen gesetzt ist und die folgenden Werte nicht
            # explizit gesetzt werden, dann sollen die Werte aus dem VP übernommen werden
            if not vals.get('efr_invoice_term_id') and res.reseller_partner_id.efr_invoice_term_id:
                res.efr_invoice_term_id = res.reseller_partner_id.efr_invoice_term_id
            if not vals.get('subscription_template_id') and res.reseller_partner_id.subscription_template_id:
                res.subscription_template_id = res.reseller_partner_id.subscription_template_id
        return res

    @job
    def job_create_efr_subscription(self):
        for partner in self:
            if partner.has_active_cash_register:
                partner.create_efr_subscription()

    def cron_create_efr_subscription(self):
        for rec in self.search([]).filtered(lambda x: x.has_active_cash_register):
            rec.with_delay().job_create_efr_subscription()

    def create_efr_subscription(self):
        for rec in self:
            subscription = self.env['sale.subscription'].search([('partner_id', '=', rec.id),
                                                                 ('check_sub', '=', True)])
            if subscription:
                raise ValidationError(("Für das Unternehmen %s existiert bereits das "
                                       "zu überprüfende Abonnement %s") % (rec.name, subscription.display_name))
            if not rec.efr_invoice_term_id:
                raise ValidationError("Für den Partner wurde keine Kondition gewählt!")
            if not rec.subscription_template_id:
                raise ValidationError("Für den Partner wurde keine Abo-Vorlage gewählt!")
            else:
                vals = {
                    'template_id': rec.subscription_template_id.id,
                    'name': rec.name + ' - ' + rec.subscription_template_id.name,
                    'partner_id': rec.id,
                    'user_id': rec.user_id.id,
                    'team_id': rec.team_id.id,
                    'date_start': fields.date.today(),
                    'description': False,
                    'pricelist_id': rec.property_product_pricelist.id,
                    'invoice_term_id': rec.efr_invoice_term_id.id,
                    'company_id': rec.company_id.id,
                    'stage_id': self.env['sale.subscription.stage'].search([], limit=1).id,
                    'recurring_next_date': fields.Date.to_date(
                        str(fields.date.today().year) + '-01-01') + relativedelta(years=1),
                    'check_sub': True,
                    'recurring_upgrades_last_date': fields.Date.to_date(str(fields.date.today().year) + '-01-01'),
                    'recurring_upgrades_next_date': fields.Date.to_date(
                        str(fields.date.today().year) + '-01-01') + relativedelta(years=1),
                }
                subscription = self.env['sale.subscription'].create(vals)
                subscription.button_update_lines()
                subscription.message_post(body="Das Abo wurde aus dem Unternehmen erstellt")
        action = self.env.ref('sale_subscription.sale_subscription_action').read()[0]
        action['context'] = "{'group_by': 'stage_id'}"
        return action
