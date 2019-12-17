# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).
import datetime
import logging
import math

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class SaleSubscription(models.Model):
    _inherit = 'sale.subscription'

    cash_register_ids = fields.One2many(related="partner_id.cash_register_ids", string="Kassen", required=True)
    invoice_term_id = fields.Many2one('efr.invoice.term', string="Konditionen", tracking=True)
    invoice_partner_id = fields.Many2one(related="partner_id.invoice_partner_id", string="Verrechnungspartner",
                                         readonly=True, store=True)
    recurring_upgrades_last_date = fields.Date(string="Letzte Nachverrechnung",
                                               help="Datum der letzten Nachverrechnung")
    recurring_upgrades_next_date = fields.Date(string="Nächste Nachverrechnung",
                                               help="Datum der nächsten Nachverrechnung")
    order_ref = fields.Char(string="Bestellreferenz", help="Dieser Wert wird auf der Rechnung angedruckt.")
    check_sub = fields.Boolean(string="Prüfung erforderlich")
    offline_sub = fields.Boolean(string="Offline-Abo")

    def _existing_invoice_domain(self):
        domain = [
            ('state', '=', 'draft'),
            ('partner_id', '=', self.invoice_partner_id.id),
            ('subscription_template_id', '=', self.template_id.id)
        ]
        if self.invoice_partner_id.single_invoice:
            domain.append(('subscription_partner_id', '=', self.partner_id.id))
        return domain

    def _recurring_create_invoice(self, automatic=False):
        # Filter Subscriptions
        for record in self:
            if not record.invoice_term_id:
                super(SaleSubscription, record)._recurring_create_invoice(automatic)
            else:
                auto_commit = self.env.context.get('auto_commit', True)
                cr = self.env.cr
                invoices = self.env['account.invoice']
                current_date = datetime.date.today()
                if len(self) > 0:
                    subscriptions = self
                else:
                    domain = [('recurring_next_date', '<=', current_date),
                              '|', ('in_progress', '=', True), ('to_renew', '=', True)]
                    subscriptions = self.with_context(not_all=True).search(domain)
                if subscriptions:
                    sub_data = subscriptions.read(fields=['id', 'company_id'])
                    for company_id in set(data['company_id'][0] for data in sub_data):
                        sub_ids = [s['id'] for s in sub_data if s['company_id'][0] == company_id]
                        subs = self.with_context(company_id=company_id, force_company=company_id).browse(sub_ids)
                        context_company = dict(self.env.context, company_id=company_id, force_company=company_id)
                        recurring_next_date = self.recurring_next_date
                        for subscription in subs:
                            # MEHRMONATLICHE ABRECHNUNG
                            if subscription.template_id.merge_invoices > 0 and subscription.template_id.recurring_rule_type == 'monthly':
                                for i in range(subscription.template_id.merge_invoices):
                                    if subscription.template_id.payment_mode in ['draft_invoice', 'manual',
                                                                                 'validate_send']:
                                        # DOMAIN TO SEARCH EXISTING INVOICES
                                        existing_invoice_domain = self._existing_invoice_domain()
                                        existing_invoice_domain.append(
                                            ('subscription_invoice_date', '=', recurring_next_date))
                                        invoices = invoices.search(existing_invoice_domain)
                                        if not invoices:
                                            try:
                                                invoice_values = subscription.with_context(
                                                    lang=subscription.partner_id.lang)._prepare_invoice()
                                                # UPDATE THE VALUES BY TWO FIELDS
                                                invoice_values.update({
                                                    'subscription_template_id': subscription.template_id.id,
                                                    'subscription_invoice_date': recurring_next_date,
                                                    'subscription_partner_id': subscription.partner_id.id
                                                })
                                                new_invoice = self.env['account.invoice'].with_context(
                                                    context_company).create(invoice_values)
                                                new_invoice.message_post_with_view(
                                                    'mail.message_origin_link',
                                                    values={'self': new_invoice, 'origin': subscription},
                                                    subtype_id=self.env.ref('mail.mt_note').id)
                                                new_invoice.with_context(context_company).compute_taxes()
                                                invoices += new_invoice
                                                next_date = subscription.recurring_next_date or current_date
                                                periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months',
                                                           'yearly': 'years'}
                                                invoicing_period = relativedelta(**{periods[
                                                                                        subscription.recurring_rule_type]: subscription.recurring_interval})
                                                new_date = next_date + invoicing_period
                                                subscription.write(
                                                    {'recurring_next_date': new_date.strftime('%Y-%m-%d')})
                                                if subscription.template_id.payment_mode == 'validate_send':
                                                    subscription.validate_and_send_invoice(new_invoice)
                                                if automatic and auto_commit:
                                                    cr.commit()
                                            except Exception:
                                                if automatic and auto_commit:
                                                    cr.rollback()
                                                    _logger.exception(
                                                        'Fail to create recurring invoice for subscription %s',
                                                        subscription.code)
                                                else:
                                                    raise
                                        else:
                                            try:
                                                invoice_values = subscription.with_context(
                                                    lang=subscription.partner_id.lang)._prepare_invoice()
                                                for key in sorted(invoice_values.keys()):
                                                    if key != 'invoice_line_ids':
                                                        invoice_values.pop(key)
                                                invoices[0].with_context(
                                                    context_company).write(invoice_values)
                                                next_date = subscription.recurring_next_date or current_date
                                                periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months',
                                                           'yearly': 'years'}
                                                invoicing_period = relativedelta(**{periods[
                                                                                        subscription.recurring_rule_type]: subscription.recurring_interval})
                                                new_date = next_date + invoicing_period
                                                subscription.write(
                                                    {'recurring_next_date': new_date.strftime('%Y-%m-%d')})
                                                if automatic and auto_commit:
                                                    cr.commit()
                                            except Exception:
                                                if automatic and auto_commit:
                                                    cr.rollback()
                                                    _logger.exception(
                                                        'Fail to create recurring invoice for subscription %s',
                                                        subscription.code)
                                                else:
                                                    raise
                                        self.button_update_lines()
                                    else:
                                        raise UserError("Die gewählte Abo-Zahlungsart wird derzeit nicht unterstützt.")
                            # MONATLICHE UND JÄHRLICHE ABRECHNUNG
                            else:
                                if subscription.template_id.payment_mode in ['draft_invoice', 'manual',
                                                                             'validate_send']:
                                    # DOMAIN TO SEARCH EXISTING INVOICES
                                    existing_invoice_domain = self._existing_invoice_domain()
                                    existing_invoice_domain.append(
                                        ('subscription_invoice_date', '=', recurring_next_date))
                                    invoices = invoices.search(existing_invoice_domain)
                                    if not invoices:
                                        try:
                                            invoice_values = subscription.with_context(
                                                lang=subscription.partner_id.lang)._prepare_invoice()
                                            # UPDATE THE VALUES BY TWO FIELDS
                                            invoice_values.update({
                                                'subscription_template_id': subscription.template_id.id,
                                                'subscription_invoice_date': recurring_next_date,
                                                'subscription_partner_id': subscription.partner_id.id
                                            })
                                            new_invoice = self.env['account.invoice'].with_context(
                                                context_company).create(invoice_values)
                                            new_invoice.message_post_with_view(
                                                'mail.message_origin_link',
                                                values={'self': new_invoice, 'origin': subscription},
                                                subtype_id=self.env.ref('mail.mt_note').id)
                                            new_invoice.with_context(context_company).compute_taxes()
                                            invoices += new_invoice
                                            next_date = subscription.recurring_next_date or current_date
                                            periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months',
                                                       'yearly': 'years'}
                                            invoicing_period = relativedelta(**{periods[
                                                                                    subscription.recurring_rule_type]: subscription.recurring_interval})
                                            new_date = next_date + invoicing_period
                                            subscription.write(
                                                {'recurring_next_date': new_date.strftime('%Y-%m-%d')})
                                            if subscription.template_id.payment_mode == 'validate_send':
                                                subscription.validate_and_send_invoice(new_invoice)
                                            if automatic and auto_commit:
                                                cr.commit()
                                        except Exception:
                                            if automatic and auto_commit:
                                                cr.rollback()
                                                _logger.exception(
                                                    'Fail to create recurring invoice for subscription %s',
                                                    subscription.code)
                                            else:
                                                raise
                                    else:
                                        try:
                                            invoice_values = subscription.with_context(
                                                lang=subscription.partner_id.lang)._prepare_invoice()
                                            for key in sorted(invoice_values.keys()):
                                                if key != 'invoice_line_ids':
                                                    invoice_values.pop(key)
                                            invoices[0].with_context(
                                                context_company).write(invoice_values)
                                            next_date = subscription.recurring_next_date or current_date
                                            periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months',
                                                       'yearly': 'years'}
                                            invoicing_period = relativedelta(**{periods[
                                                                                    subscription.recurring_rule_type]: subscription.recurring_interval})
                                            new_date = next_date + invoicing_period
                                            subscription.write(
                                                {'recurring_next_date': new_date.strftime('%Y-%m-%d')})
                                            if automatic and auto_commit:
                                                cr.commit()
                                        except Exception:
                                            if automatic and auto_commit:
                                                cr.rollback()
                                                _logger.exception(
                                                    'Fail to create recurring invoice for subscription %s',
                                                    subscription.code)
                                            else:
                                                raise
                                    self.button_update_lines()
                                else:
                                    raise UserError("Die gewählte Abo-Zahlungsart wird derzeit nicht unterstützt.")
                                self.button_update_lines()
                return invoices

    def search(self, args, offset=0, limit=None, order=None, count=False):
        if self.env.context.get('not_all'):
            args.append(('invoice_term_id', '!=', False))
        return super(SaleSubscription, self).search(args, offset, limit, order, count)

    def _prepare_invoice_data(self):
        res = super(SaleSubscription, self)._prepare_invoice_data()
        if self.invoice_term_id:
            res.update({'comment': '' or False})
        # IF PARTNER ID != INVOICE PARTNER_ID
        if self.partner_id != self.invoice_partner_id:
            res.update({
                'partner_id': self.invoice_partner_id.id
            })
        return res

    def _prepare_invoice_lines(self, fiscal_position):
        res = super(SaleSubscription, self)._prepare_invoice_lines(fiscal_position)
        if self.partner_id != self.invoice_partner_id:
            res.insert(0, (0, 0, {'name': self.partner_id.name + (' - VAT ' + str(self.partner_id.vat)
                                                                  if self.partner_id.vat else ""),
                                  'display_type': 'line_section'}))
        if self.template_id.recurring_rule_type == 'monthly' and self.recurring_next_date.month != 1:
            for kassa in self.cash_register_ids.filtered(
                    lambda x: x.date_start.day <= 15 and x.date_start.month == self.recurring_next_date.month - 1 and
                              x.date_start.year == self.recurring_next_date.year):
                for line in self.invoice_term_id.line_ids:
                    start_date = format_date(self.env, kassa.date_start)
                    end_date = format_date(self.env, kassa.date_start + relativedelta(months=1) - relativedelta(
                        days=kassa.date_start.day))
                    res.append((0, 0, {
                        'name': line.product_id.name + '\n' + 'Leistungszeitraum: ' + start_date + ' - ' + end_date,
                        'account_id': line.product_id.property_account_income_id.id,
                        'subscription_id': self.id,
                        'account_analytic_id': self.analytic_account_id,
                        'price_unit': line.price_unit,
                        'quantity': 1,
                        'uom_id': line.product_id.uom_id.id,
                        'product_id': line.product_id.id,
                        'invoice_line_tax_ids': [(6, 0, line.product_id.taxes_id.ids)],
                        'analytic_tag_ids': [(6, 0, self.analytic_account_id.line_ids.mapped('tag_ids').ids)]
                    }))
        return res

    def _prepare_invoice_line(self, line, fiscal_position):
        res = super(SaleSubscription, self)._prepare_invoice_line(line, fiscal_position)
        next_date = fields.Date.from_string(self.recurring_next_date)
        if not next_date:
            raise UserError(_('Please define Date of Next Invoice of "%s".') % (self.display_name,))
        periods = {'daily': 'days', 'weekly': 'weeks', 'monthly': 'months', 'yearly': 'years'}
        end_date = next_date + relativedelta(**{periods[self.recurring_rule_type]: self.recurring_interval})
        end_date = end_date - relativedelta(days=1)  # remove 1 day as normal people thinks in term of inclusive ranges.
        if self.invoice_term_id:
            res['name'] += "\nLeistungszeitraum: %s - %s" % (
                format_date(self.env, next_date), format_date(self.env, end_date))
        return res

    # UPDATE DER ZEILEN mit den Produkten aus den Konditionszeilen * Anzahl der aktiven Kassen
    def button_update_lines(self):
        date = self.recurring_next_date
        cash_register_count = len(self.cash_register_ids.filtered(
            lambda x: x.date_start < date and (x.date_end == False or x.date_end >= date)))
        for line in self.invoice_term_id.line_ids:
            if line.product_id in self.recurring_invoice_line_ids.filtered(
                    lambda x: x.product_id.id == line.product_id.id).mapped('product_id'):
                for product in self.recurring_invoice_line_ids.filtered(
                        lambda x: x.product_id.id == line.product_id.id):
                    if product.quantity != cash_register_count:
                        product.update({
                            'price_unit': line.price_unit,
                            'quantity': cash_register_count,
                        })
            else:
                self.recurring_invoice_line_ids.create({
                    'name': line.product_id.name,
                    'price_unit': line.price_unit,
                    'quantity': cash_register_count,
                    'uom_id': line.product_id.uom_id.id,
                    'product_id': line.product_id.id,
                    'analytic_account_id': self.id
                })

    def _get_active_cashregisters(self, date_from, date_to):
        cash_registers = self.cash_register_ids.filtered(
            lambda x: x.date_start <= date_to and (not x.date_end or x.date_end >= date_from))
        return cash_registers

    def _get_active_locations(self, date_from, date_to):
        locations = self.cash_register_ids.filtered(
            lambda x: x.date_start <= date_to and (not x.date_end or x.date_end >= date_from)).mapped(
            'location_id')
        return locations

    # Berechnung der Anzahl der zu verrechnenden Archiv-Upgrades
    def get_upgrade_invoice_qty(self, date_from, date_to, kassa=False, location=False, partner=False):
        cash_registers = self.cash_register_ids.filtered(
            lambda x: x.date_start <= date_to and (not x.date_end or x.date_end >= date_from) and (
                x.id == kassa.id if kassa else False or x.location_id.id == location.id if location else False))
        if not kassa and not location:
            cash_registers = self.cash_register_ids.filtered(
                lambda x: x.date_start <= date_to and (not x.date_end or x.date_end >= date_from))
        total_months = 0
        for cash_register in cash_registers:
            if cash_register.date_end:
                date_to = cash_register.date_end
            start_month = cash_register.date_start.month
            if cash_register.date_start.year != date_to.year:
                start_month = 1
            while start_month <= date_to.month:
                total_months += 1
                start_month += 1
        if total_months > 12:
            total_months = 12
        transaction_domain = [('period', '>=', date_from), ('period', '<=', date_to)]
        if kassa:
            transaction_domain.append(('cash_register_id', '=', kassa.id))
        if location:
            transaction_domain.append(('cash_register_id.location_id', '=', location.id))
        if not kassa and not location:
            transaction_domain.append(('partner_id', '=', partner.id))
        transactions = self.env['efr.transactions'].search(transaction_domain)
        actual_transactions = 0
        included_transactions = self.invoice_term_id.included_transactions
        for transaction in transactions:
            actual_transactions += transaction.qty
        if len(cash_registers) > 1:
            included_transactions = included_transactions * len(cash_registers)
        exceed = (included_transactions / 12) * total_months - actual_transactions
        output = 0
        # Inkludierte Transaktionen zurück auf die Ursprungsanzahl setzen, damit die Berechnung stimmt
        included_transactions = self.invoice_term_id.included_transactions
        if included_transactions == 0 or actual_transactions == 0:
            output = 0
        if exceed < 0:
            exceed = abs(exceed)
            output = math.ceil(exceed / included_transactions)
        return output

    def action_invoice_upgrades(self):
        for rec in self:
            if rec.invoice_term_id:
                invoice_lines = []
                # Überprüfung, ob neue Kassen für den Zeitraum dazu gekommen sind, gegebenfalls in die
                # Rechnung hinzufügen
                new_cashregister_lines = rec.prepare_new_cashregister_lines()
                if new_cashregister_lines:
                    for line in new_cashregister_lines:
                        invoice_lines.append(line)
                date_from = rec.recurring_upgrades_last_date
                date_to = rec.recurring_upgrades_next_date - relativedelta(days=1)

                # Wenn das Flag 'Unbegrenzte Anzahl an Transaktionen' nicht gesetzt ist, werden die Archiv-Upgrades
                # berechnet
                if not rec.invoice_term_id.unlimited_transactions:
                    if rec.invoice_term_id.type_upgrade == 'cash_register':
                        for k in rec._get_active_cashregisters(date_from, date_to):
                            to_invoice_qty = rec.get_upgrade_invoice_qty(date_from, date_to, kassa=k)
                            upgrade_invoice_lines = rec.prepare_upgrade_invoice_lines(to_invoice_qty,
                                                                                      "Kassa %s" % k.portal_id)
                            if upgrade_invoice_lines:
                                invoice_lines.append(upgrade_invoice_lines)

                    if rec.invoice_term_id.type_upgrade == 'location':
                        for s in rec._get_active_locations(date_from, date_to):
                            to_invoice_qty = rec.get_upgrade_invoice_qty(date_from, date_to, kassa=False, location=s)
                            upgrade_invoice_lines = rec.prepare_upgrade_invoice_lines(to_invoice_qty,
                                                                                      "Standort %s" % s.name)
                            if upgrade_invoice_lines:
                                invoice_lines.append(upgrade_invoice_lines)

                    if rec.invoice_term_id.type_upgrade == 'company':
                        to_invoice_qty = rec.get_upgrade_invoice_qty(date_from, date_to, partner=rec.partner_id)
                        upgrade_invoice_lines = rec.prepare_upgrade_invoice_lines(to_invoice_qty, "Unternehmensweit")
                        if upgrade_invoice_lines:
                            invoice_lines.append(upgrade_invoice_lines)

                # Die Rechnungszeilen nach Unternehmen aufteilen, in dem eine Überschrift hinzugefügt wird
                if invoice_lines:
                    invoice_lines.insert(0, (0, 0, {'name': rec.partner_id.name + (
                        ' - VAT ' + str(rec.partner_id.vat) if rec.partner_id.vat else ""),
                                                    'display_type': 'line_section'}))

                rec.invoice_nachverrechnung(invoice_lines)
                rec.recurring_upgrades_last_date = rec.recurring_upgrades_next_date
                rec.recurring_upgrades_next_date = rec.recurring_upgrades_next_date + relativedelta(years=1)

    def cron_invoice_upgrades(self):
        subscriptions = self.search([('recurring_upgrades_next_date', '<=', fields.Date.today())])
        # TODO pro 10 Abos:
        for sub in subscriptions:
            sub.action_invoice_upgrades()
            self._cr.commit()

    def button_invoice_upgrades(self):
        self.action_invoice_upgrades()
        return self.action_subscription_invoice()

    def invoice_nachverrechnung(self, invoice_lines):
        # Rechnung erstellen und die Zeilen befüllen, falls es eine existierende Rechnung gibt, werden die Zeilen dort hinzugefügt
        existing_invoice_domain = self._existing_invoice_domain()
        existing_invoice_domain.pop(2)
        existing_invoice_domain.append(('is_subsequent', '=', True))
        existing_invoice_domain.append(('date_invoice', '=', self.recurring_upgrades_next_date))

        inv = self.env['account.invoice'].search(existing_invoice_domain)
        if not inv:
            inv = self.env['account.invoice'].create(self._prepare_invoice_data())
            inv.is_subsequent = True
            inv.date_invoice = self.recurring_upgrades_next_date
            inv.subscription_partner_id = self.partner_id.id
        inv = inv[0]
        inv.invoice_line_ids = invoice_lines

    def prepare_new_cashregister_lines(self):
        # Überprüfung, ob neue Kassen dazugekommen sind
        if not self.recurring_upgrades_last_date:
            raise UserError("Das Feld 'Letzte Nachverrechnung' ist nicht gesetzt!")
        if not self.recurring_upgrades_next_date:
            raise UserError("Das Feld 'Nächste Nachverrechnung' ist nicht gesetzt!")
        if self.template_id.recurring_rule_type == 'yearly':
            last_billing = self.recurring_upgrades_next_date - relativedelta(years=1)
        elif self.template_id.recurring_rule_type == 'monthly':
            last_billing = self.recurring_upgrades_next_date - relativedelta(months=1)
        else:
            raise NotImplemented
        invoice_line_dict = []
        for k in self.cash_register_ids.filtered(
                lambda x: x.date_start >= last_billing and x.date_start <= self.recurring_upgrades_next_date):
            for l in self.invoice_term_id.line_ids:
                date_to = self.recurring_upgrades_next_date - relativedelta(days=1)
                months_count = 0
                start_month = k.date_start.month
                while start_month <= date_to.month:
                    months_count += 1
                    start_month += 1
                if k.date_start.day > 15:
                    months_count -= 1

                if months_count > 0:
                    von = format_date(self.env, k.date_start)
                    invoice_line_dict.append({
                        'name': l.product_id.name + "\nLeistungszeitraum: " + von + " - " + "31.12." + str(
                            k.date_start.year),
                        'account_id': l.product_id.property_account_income_id.id,
                        'subscription_id': self.id,
                        'account_analytic_id': self.analytic_account_id.id,
                        'price_unit': l.price_unit * months_count / 12 if self.template_id.recurring_rule_type == 'yearly' else l.price_unit,
                        'quantity': 1,
                        'uom_id': l.product_id.uom_id.id,
                        'product_id': l.product_id.id,
                        'invoice_line_tax_ids': [(6, 0, l.product_id.taxes_id.ids)],
                        'analytic_tag_ids': [(6, 0, self.analytic_account_id.line_ids.mapped('tag_ids').ids)]
                    })
        return invoice_line_dict

    def prepare_upgrade_invoice_lines(self, to_invoice_qty, text):
        # Erstellen der Archiv-Upgrade Zeilen
        if to_invoice_qty == 0:
            return
        von = format_date(self.env, self.recurring_upgrades_last_date)
        bis = format_date(self.env, self.recurring_upgrades_next_date - relativedelta(days=1))
        return {
            'name': self.invoice_term_id.upgrade_product_id.name + "\nTransaktionsüberschreitung für:\n" + text + "\nLeistungszeitraum: " +
                    von + " - " + bis,
            'account_id': self.invoice_term_id.upgrade_product_id.property_account_income_id.id,
            'subscription_id': self.id,
            'account_analytic_id': self.analytic_account_id.id,
            'price_unit': self.invoice_term_id.upgrade_unit_price,
            'quantity': to_invoice_qty,
            'uom_id': self.invoice_term_id.upgrade_product_id.uom_id.id,
            'product_id': self.invoice_term_id.upgrade_product_id.id,
            'invoice_line_tax_ids': [(6, 0, self.invoice_term_id.upgrade_product_id.taxes_id.ids)],
            'analytic_tag_ids': [(6, 0, self.analytic_account_id.line_ids.mapped('tag_ids').ids)]
        }


class SaleSubscriptionTemplate(models.Model):
    _inherit = 'sale.subscription.template'

    merge_invoices = fields.Integer("Rechnungen zusammenfassen", default=0,
                                    help="Um z.B. eine Quartalsweise Abrechnung zu konfigurieren, wird die Periode "
                                         "auf 1 Monat gesetzt und dieser Wert auf 3", tracking=True)


class SaleSubscriptionLine(models.Model):
    _inherit = 'sale.subscription.line'

    efr_location_id = fields.Many2one('efr.location', string="Standort",
                                      domain=[("partner_id", "=", "parent.partner_id")])
