# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).
import base64
import calendar
import csv
import io
from collections import OrderedDict
from datetime import datetime, date
from odoo.exceptions import Warning

from odoo import api, fields, models

from .. import dp_tools

FIELDNAMES_FAKTURA = [
    'satzart',
    'konto',
    'gkonto',
    'belegnr',
    'buchdatum',
    'belegdatum',
    'buchsymbol',
    'buchcode',
    'steuercode',
    'betrag',
    'prozent',
    'steuer',
    'text'
]

FIELDNAMES_CUSTOMER = [
    'ktonr',
    'nachname',
    'land',
    'plz',
    'ort',
    'strasse',
    'uidnummer',
    'mail',
]


def _localize_floats(val):
    return str(val).replace('.', ',') if isinstance(val, float) else val


def _preprocess_output_row(dictionary):
    for key in dictionary:
        # remove False with ' '
        if str(dictionary[key]) == 'False':
            dictionary[key] = ' '
        # Ersetze '.' durch ','
        dictionary[key] = _localize_floats(dictionary[key])
    return dictionary


class BmdExportWizard(models.TransientModel):
    _name = 'bmd.export.wizard'
    _description = 'BMD Export Wizard'

    def _default_date_begin(self):
        ts = dp_tools.first_day_of_current_month()
        return fields.Date.to_string(ts)

    def _default_date_end(self):
        ts = dp_tools.last_day_of_current_month()
        return fields.Date.to_string(ts)

    TYPE = [
        ('unexported', 'Alle noch nicht exportierten Daten'),
        ('date_range', 'Datumsbereich'),
    ]

    type = fields.Selection(TYPE, string='Typ', default='unexported')
    date_begin = fields.Date(string='Datum von', default=_default_date_begin)
    date_end = fields.Date(string='Datum bis', default=_default_date_end)
    group = fields.Boolean(string='Nach Kostenstelle gruppieren', default=True)

    @api.multi
    def do_export(self):
        self.ensure_one()

        if self.type == 'date_range':
            date_begin = fields.Date.from_string(self.date_begin)
            date_begin = dp_tools.utc_start_of_day(date_begin)

            date_end = fields.Date.from_string(self.date_end)
            date_end = dp_tools.utc_end_of_day(date_end)
        else:
            date_begin = False
            date_end = False

        vals = {
            'name': fields.Datetime.now(),
            'user_id': self.env.user.id,
            'type': self.type,
            'date_begin': date_begin,
            'date_end': date_end,
        }

        export = self.env['bmd.export'].create(vals)
        invoice_data, invoice_count = self.get_invoice_data()
        export.invoice_count = invoice_count
        timestamp = datetime.today().strftime('%Y-%m-%d')
        filename = '%s_%s.csv' % ('invoices', timestamp)

        ir_attachment = {
            'type': 'binary',
            'name': filename,
            'datas_fname': filename,
            'datas': self.to_csv(invoice_data, 'account.invoice'),
            'res_model': 'bmd.export',
            'res_id': export.id,
        }
        self.env['ir.attachment'].create(ir_attachment)

        customer_data, customer_count = self.get_customer_data()
        export.customer_count = customer_count
        timestamp = datetime.today().strftime('%Y-%m-%d')
        filename_customer = '%s_%s.csv' % ('customers', timestamp)

        customer_attachment_vals = {
            'type': 'binary',
            'name': filename_customer,
            'datas_fname': filename_customer,
            'datas': self.to_csv(customer_data, 'res.partner'),
            'res_model': 'bmd.export',
            'res_id': export.id,
        }
        self.env['ir.attachment'].create(customer_attachment_vals)

        bmd_invoices = []
        if self.type == 'unexported':
            bmd_invoices = self.env['account.invoice'].search(
                [('bmd_export', '=', True), ('state', 'in', ['open', 'paid'])])
        elif self.type == 'date_range':
            bmd_invoices = self.env['account.invoice'].search(
                [('date_invoice', '<', self.date_end), ('date_invoice', '>', self.date_begin),
                 ('state', 'in', ['open', 'paid'])])
        if bmd_invoices:
            for inv in bmd_invoices:
                inv.bmd_export = False

        return {
            'name': 'Export-Dateien',
            'view_mode': 'form',
            'view_id': self.env.ref('dp_bmd.view_bmd_export_form').id,
            'res_model': 'bmd.export',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': export.id,
        }

    @api.multi
    def get_invoice_data(self):
        grouping = {}
        invoice_count = 0
        invoice_list = []
        if self.type == 'unexported':
            domain = [
                ('bmd_export', '=', True),
                ('state', 'in', ['open', 'paid'])
            ]
            invoices = self.env['account.invoice'].search(domain)
            invoices.sorted(key=lambda r: r.date_invoice)

            for inv in invoices:
                # if inv.type == 'in_invoice' or inv.type == 'in_refund':
                #     continue

                invoice_count += 1
                for line in inv.invoice_line_ids:
                    # if the group flag was set in the wizard
                    if self.group:
                        row = self.get_row_faktura(inv, line)
                        key = self.generate_key_faktura(row)
                        if key in grouping:
                            grow = grouping[key]
                            grow['betrag'] = grow['betrag'] + row['betrag']
                            grow['steuer'] = grow['steuer'] + row['steuer']
                            grouping[key] = grow
                        else:
                            grouping[key] = row
                    else:
                        invoice_list.append(_preprocess_output_row(self.get_row_faktura(inv, line)))
                inv.bmd_export_date = date.today().strftime('%Y-%m-%d')
            if self.group:
                sorted_grouped_invoice_lines = sorted(grouping.items(),
                                                      key=lambda x: datetime.strptime(x[1]['belegdatum'], '%d.%m.%Y'))
                for row in sorted_grouped_invoice_lines:
                    invoice_list.append(_preprocess_output_row(row[1]))
            return invoice_list, invoice_count

        elif self.type == 'date_range':
            domain = [
                ('date_invoice', '<', self.date_end),
                ('date_invoice', '>', self.date_begin),
                ('state', 'in', ['open', 'paid'])
            ]
            invoices = self.env['account.invoice'].search(domain)
            invoices.sorted(key=lambda r: r.date_invoice)

            for inv in invoices:
                # if inv.type == 'in_invoice' or inv.type == 'in_refund':
                #     continue

                invoice_count += 1
                for line in inv.invoice_line_ids:
                    # if the group flag was set in the wizard
                    if self.group:
                        row = self.get_row_faktura(inv, line)
                        key = self.generate_key_faktura(row)
                        if key in grouping:
                            grow = grouping[key]
                            grow['betrag'] = grow['betrag'] + row['betrag']
                            grow['steuer'] = grow['steuer'] + row['steuer']
                            grouping[key] = grow
                        else:
                            grouping[key] = row
                    else:
                        invoice_list.append(_preprocess_output_row(self.get_row_faktura(inv, line)))
                inv.bmd_export_date = date.today().strftime('%Y-%m-%d')
            if self.group:
                sorted_grouped_invoice_lines = sorted(grouping.items(),
                                                      key=lambda x: datetime.strptime(x[1]['belegdatum'], '%d.%m.%Y'))
                for row in sorted_grouped_invoice_lines:
                    invoice_list.append(_preprocess_output_row(row[1]))
            return invoice_list, invoice_count

    @api.multi
    def get_customer_data(self):
        customer_count = 0
        customer_list = []
        if self.type == 'unexported':
            domain = [
                ('bmd_export', '=', True)
            ]
            customers = self.env['res.partner'].search(domain)

            duplicate = []
            for customer in customers:
                if customer.id not in duplicate:
                    customer_count += 1
                    customer_list.append(self.get_row_customer(customer))
                    customer.bmd_export_date = date.today().strftime('%Y-%m-%d')
                    customer.bmd_export = False
                    duplicate.append(customer.id)

        elif self.type == 'date_range':
            domain = [
                ('date_invoice', '<', self.date_end),
                ('date_invoice', '>', self.date_begin),
                ('state', 'in', ['open', 'paid'])
            ]
            invoices = self.env['account.invoice'].search(domain)

            duplicate = []
            for inv in invoices:
                commercial_partner = inv.partner_id.commercial_partner_id
                if commercial_partner and commercial_partner.id not in duplicate:
                    customer_count += 1
                    customer_list.append(self.get_row_customer(commercial_partner))
                    commercial_partner.bmd_export_date = date.today().strftime('%Y-%m-%d')
                    duplicate.append(commercial_partner.id)
        return customer_list, customer_count

    def to_csv(self, data_list, model='account.invoice'):
        fieldnames = FIELDNAMES_FAKTURA
        if model == 'res.partner':
            fieldnames = FIELDNAMES_CUSTOMER

        with io.StringIO(newline='') as f:
            writer = csv.DictWriter(f, fieldnames, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            for row in data_list:
                writer.writerow(row)
            return base64.b64encode(f.getvalue().encode('latin-1'))

    @api.multi
    def get_row_faktura(self, inv, line):
        faktura_dict = OrderedDict()

        faktura_dict['satzart'] = 0
        faktura_dict['konto'] = line.account_id.code
        faktura_dict['gkonto'] = inv.account_id.code
        faktura_dict['belegnr'] = inv.number

        # invoice_date = datetime.strptime(inv.date_invoice, '%Y-%m-%d')
        # end_of_month = invoice_date.replace(day=calendar.monthrange(invoice_date.year, invoice_date.month)[1])
        end_of_month = inv.date_invoice.replace(
            day=calendar.monthrange(inv.date_invoice.year, inv.date_invoice.month)[1])
        faktura_dict['buchdatum'] = end_of_month.strftime('%d.%m.%Y')
        # faktura_dict['belegdatum'] = invoice_date.strftime('%d.%m.%Y')
        faktura_dict['belegdatum'] = inv.date_invoice.strftime('%d.%m.%Y')

        if inv.type == 'out_invoice':
            faktura_dict['buchsymbol'] = 'AR'
        elif inv.type == 'out_refund':
            faktura_dict['buchsymbol'] = 'GU'
        elif inv.type == 'in_invoice':
            faktura_dict['buchsymbol'] = 'ER'
        elif inv.type == 'in_refund':
            faktura_dict['buchsymbol'] = 'EG'

        faktura_dict['buchcode'] = 1

        if not line.invoice_line_tax_ids or len(line.invoice_line_tax_ids) == 0:
            raise Warning(u"Rechnung %s enthält Rechnungszeilen ohne Steuersatz" % inv.number)
        if line.invoice_line_tax_ids[0].bmd_tax_code:
            faktura_dict['steuercode'] = line.invoice_line_tax_ids[0].bmd_tax_code
        else:
            faktura_dict['steuercode'] = 1

        faktura_dict['betrag'] = line.price_total
        faktura_dict['prozent'] = line.invoice_line_tax_ids[0].amount

        if inv.type in ['out_invoice', 'in_refund']:
            value = (line.price_subtotal * line.invoice_line_tax_ids[0].amount / 100) * -1
            faktura_dict['steuer'] = round(inv.currency_id.round(value), 2)
        else:
            value = line.price_subtotal * line.invoice_line_tax_ids[0].amount / 100
            faktura_dict['steuer'] = round(inv.currency_id.round(value), 2)
            faktura_dict['betrag'] = -faktura_dict['betrag']

        faktura_dict['text'] = ' '

        return faktura_dict

    @api.multi
    def get_row_customer(self, customer):
        customers_dict = OrderedDict()

        customers_dict['ktonr'] = customer.property_account_receivable_id.code
        customers_dict['nachname'] = customer.name
        customers_dict['land'] = customer.country_id.code
        customers_dict['plz'] = customer.zip
        customers_dict['ort'] = customer.city
        customers_dict['strasse'] = customer.street
        customers_dict['uidnummer'] = customer.vat
        customers_dict['mail'] = customer.email

        # remove False with ' '
        for key in customers_dict:
            if str(customers_dict[key]) == 'False':
                customers_dict[key] = ' '

        return customers_dict

    def generate_key_faktura(self, od):
        gkonto = od['gkonto']
        belegnr = od['belegnr']
        steuercode = od['steuercode']
        prozent = od['prozent']

        key = str(gkonto) + '_' + str(belegnr) + '_' + str(steuercode) + '_' + str(prozent)

        return key
