# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import json
import io
import base64
import shutil
import re
import os
import uuid
import logging
from datetime import datetime
from zipfile import ZipFile
from collections import OrderedDict

from odoo import api, fields, models, tools, _ as TRANS
from odoo.tools import pycompat
from odoo.exceptions import UserError, ValidationError
from odoo.addons.web.controllers.main import CSVExport, Export

_logger = logging.getLogger(__name__)

# TODO für multi-company: für alle relevanten models "company_id/id" hinzufügen
# TODO wenn "search_fields" angegeben, dann auch die XMLID exportieren. Beim Import dann nur suchen wenn die XMLID nicht vorhanden ist.
# TODO Ablgleich der zu exportierenden Felder. Nur die Felder exportieren, die es auch tatsächlich gibt (nicht in allen Setups gibt es alle Felder)
# TODO Alle Objekte in der Oberfläche als "Konfigurationswert" kennzeichnen, sodass man auch andere Objekte wie zB Produkte mitnehmen kann
# TODO ir.sequence XML-IDs


# Wenn die Configwerte des Odoo-Servers unter diesen Werten liegen, so werden diese während des Imports und Exports
# auf diese Werte angehoben

CONFIG_LIMITS = [('limit_time_cpu', 36000), # 10h
                 ('limit_time_real', 36000), # 10h
                 ('limit_memory_soft', 5000000000), # 5GB
                ]

STUDIO_FILE = 'customizations.zip'
CONFIG_FILE = 'odoo-config.json'
FAVICON = 'images/favicon.ico'
COMPANY_LOGO = 'images/company_logo.png'
CONFIG_EXCLUDE_FIELDS = ['id', 'account_bank_reconciliation_start', 'last_currency_sync_date',
                         'tax_cash_basis_journal_id/id', 'currency_exchange_journal_id/id',
                         'currency_next_execution_date', 'default_sale_order_template_id/id',
                         'leave_timesheet_task_id/id', 'deposit_default_product_id/id', 'leave_timesheet_project_id/id']
XMLIDS = {
    # stock
    'warehouse_location_id': '__dp__.warehouse_location',
    'qc_location_id': '__dp__.qc_location',
    'in_sequence': '__dp__.in_sequence',
    'out_sequence': '__dp__.out_sequence',
    'pack_sequence': '__dp__.pack_sequence',
    'pick_sequence': '__dp__.pick_sequence',
    'int_sequence': '__dp__.int_sequence',
    'reception_route': '__dp__.reception_route',
    'delivery_route': '__dp__.delivery_route',
    'crossdock_route': '__dp__.crossdock_route',
    'pick_type': '__dp__.pick_type',
    'pack_type': '__dp__.pack_type',
    'transit_location': '__dp__.transit_location',

    # mrp
    'pbm_type': '__dp__.pbm_type',
    'sam_type': '__dp__.sam_type',
    'manu_type': '__dp__.manu_type',
    'pbm_sequence': '__dp__.pbm_sequence',
    'sam_sequence': '__dp__.sam_sequence',
    'manu_sequence': '__dp__.manu_sequence',
    'pbm_loc': '__dp__.pbm_loc',
    'sam_loc': '__dp__.sam_loc',
    'pbm_route': '__dp__.pbm_route',

    # account
    'sale_journal': '__dp__.sales_journal',
    'purchase_journal': '__dp__.purchase_journal',
    'bank_journal': '__dp__.bank_journal',
    'cash_journal': '__dp__.cash_journal',
    'sale_sequence': '__dp__.sale_sequence',
    'purchase_sequence': '__dp__.purchase_sequence',
    'bank_sequence': '__dp__.bank_sequence',
    'cash_sequence': '__dp__.cash_sequence',
    'unaffected_earnings_account': '__dp__.unaffected_earnings_account',
    'bank_account': '__dp__.bank_account',
    'cash_account': '__dp__.cash_account',
}

CONFIG_MODELS = OrderedDict([
    ('ir.model.fields', {
        'fields': ['name', 'field_description', 'model_id/id', 'ttype', 'help', 'required', 'readonly', 'store',
                   'index', 'copied', 'track_visibility', 'related', 'depends', 'compute', 'groups/id', 'selection',
                   'relation', 'relation_field', 'relation_table', 'column1', 'column2', 'domain', 'on_delete', 'size',
                   'translate'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User, Partner-ID 1 ist company
        'search_fields': ['model_id', 'name'],
    }),
    ('res.bank', {
        'fields': ['id', 'name', 'bic'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User, Partner-ID 1 ist company
    }),
    ('res.partner.bank', {
        'fields': ['acc_number', 'acc_type', 'partner_id', 'bank_id/id', 'acc_holder_name', 'company_id/id'],
        'domain': [('partner_id', '=', 1), ('write_uid', '!=', 1)],  # 1 ist der OdooBot User, Partner-ID 1 ist company
        'search_fields': ['partner_id', 'acc_number', 'company_id']
    }),
    ('ir.sequence', {
        'fields': ['id', 'name', 'suffix', 'implementation', 'prefix', 'number_increment', 'code', 'padding',
                   'use_date_range', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    # mail.atchall.domain: hier kommt es zu einem Fehler wenn man "false" setzen möchte
    # database.*: wird nicht in die Konfig übernommen (zB 'database.secret')
    ('ir.config_parameter', {
        'fields': ['key', 'value'],
        'domain': [('write_uid', '!=', 1), ('key', 'not in', ['mail.catchall.domain', 'web.base.url']),
                   ('key', 'not ilike', 'database.')],  # 1 ist der OdooBot User
        'search_fields': ['key']
    }),
    ('account.payment.term', {
        'fields': ['id', 'name', 'active', 'note', 'sequence', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    ('account.payment.term.line', {
        'fields': ['payment_id/id', 'days', 'day_of_the_month', 'option', 'sequence', 'value', 'value_amount'],
        'replace': True,
    }),
    ('res.company', {
        'fields': ['id', 'name', 'street', 'street2', 'city', 'zip', 'phone', 'email', 'website', 'vat',
                   'company_registry',
                   'country_id/id'],
        'domain': [('id', '=', 1)],
    }),
    ('account.tax', {
        'fields': ['id', 'name', 'type_tax_use', 'amount_type', 'amount', 'description', 'tax_group_id/id',
                   'tag_ids/id', 'active', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    ('account.account', {
        # Open Issue on Github: https://github.com/odoo/odoo/issues/29326
        # 'fields': ['id', 'code', 'name', 'user_type_id/id', 'reconcile', 'deprecated'],
        'fields': ['id', 'code', 'name', 'user_type_id/id', 'deprecated', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    ('account.journal', {
        'fields': ['id', 'name', 'active', 'type', 'code', 'refund_sequence', 'group_invoice_lines', 'sequence_id/id',
                   'company_id/id'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    ('account.fiscal.position', {
        'fields': ['id', 'name', 'auto_apply', 'vat_required', 'country_group_id/id', 'country_id/id', 'active',
                   'company_id/id'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    ('account.fiscal.position.tax', {
        'fields': ['position_id/id', 'tax_src_id/id', 'tax_dest_id/id'],
        'replace': True
    }),
    ('account.fiscal.position.account', {
        'fields': ['position_id/id', 'account_src_id/id', 'account_dest_id/id'],
        'replace': True
    }),
    ('res.groups', {
        'fields': ['id', 'category_id/id', 'share', 'name', 'implied_ids/id', 'comment'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    ('ir.model.access', {
        'fields': ['id', 'name', 'model_id/id', 'group_id/id', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    ('ir.rule', {
        'fields': ['id', 'name', 'active', 'model_id/id', 'domain_force', 'groups/id', 'perm_read', 'perm_write',
                   'perm_create', 'perm_unlink'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    ('stock.warehouse', {
        'fields': ['id', 'name', 'active', 'code', 'reception_steps', 'delivery_steps', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    # Info: Alle Standardlagerorte haben eine XML-ID
    ('stock.location', {
        'fields': ['id', 'name', 'active', 'location_id/id', 'usage', 'partner_id/id', 'scrap_location',
                   'return_location', 'removal_strategy_id/id', 'posx', 'posy', 'posz', 'barcode', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    # Info: nur "Anlieferung", "Auslieferung" und "Intere Transfers" und optional "Drop Shipping" haben eine XML-ID, andere nicht
    # TODO Bei Auslieferung in 2 Schritten wird aktuelle der Vorgangstyp doppelt angelegt
    # Option 1: muss manuell gelöscht werden (kommt aber in anderne Objekten vor)
    # Option 2: optional suche mittels search_fields, wenn es keine XML-ID gibt
    # Option 3: nicht exportieren, da wir davon ausgehen, dass diese bereits existieren
    #            Nachteil: bestehende PickingTypes können auch geändert werden
    # Option 4: Definition, dass Prozesse mit 2 oder 3 Schritten nicht unterstützt werden
    # Entscheidung 4.11.: Option 4
    ('stock.picking.type', {
        'fields': ['id', 'name', 'active', 'barcode', 'code', 'return_picking_type_id/id', 'show_operations',
                   'show_reserved', 'use_create_lots', 'use_existing_lots', 'default_location_src_id/id',
                   'default_location_dest_id/id', 'sequence_id/id'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    # UC1: Ändern einer vom System angelegten Route
    # UC2: Hinzufügen einer neuen Route [OK]
    # UC3: Ändern einer bereits hinzugefügten Route
    #
    # Info: Die Standardrouten haben eine XMLID (Einkaufen, Beschaffe von Auftrag), auch Dropshipping
    #       Routen für 1-step, 2-step oder 3-step haben keine XML-ID
    ('stock.location.route', {
        'fields': ['id', 'name', 'active', 'sequence', 'product_categ_selectable', 'product_selectable',
                   'warehouse_selectable', 'warehouse_ids/id', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)],  # 1 ist der OdooBot User
    }),
    # UC1: Ändern einer vom System angelegten Regel [OK]
    # UC2: Hinzufügen einer neuen Regel [OK]
    # UC3: Ändern einer bereits hinzugefügten Regel [OK]
    # TODO Matching zu einer Route (welche keine XML-ID hat)
    # Option 1: eindeutige XMLID bereits beim Setup erzeugen (die dann immer gleich ist)
    #           Nachteil: es muss sichergestellt sein, dass beim Import bereits das Modul installiert ist
    # Option 2: Zuordnung immer dynamisch zuordnen auf Basis bestimmter Gegebenheiten
    # Option 3: Beim ersten Import einen Wizard zur Zuordnung der XML-ID bereitstellen
    # Option 4: Alle lagerrelevanten Objekte immer komplett ersetzen (die beiden Optionen im Warehouse werden nicht gesetzt)
    #           Nachteil: Routen, wie zB Einkauf sind schon in Verwendung??
    # Option 5: Verwendung von "picking_type_id" anstatt "picking_type_id/id" (es wird dann mit name_search() gesucht)
    # Option 5: Definition, dass Prozesse mit 2 oder 3 Schritten nicht unterstützt werden
    # TODO Matching zu einem PickingType (welcher keine XML-ID hat)
    # Info: Keine Regel hat eine XML-ID
    # Entscheidung 4.11.: Option 5 (Zuordnung von pickingType und Route erfolgt mittels XMLID
    ('stock.rule', {
        'fields': ['active', 'name', 'action', 'auto', 'picking_type_id/id', 'location_src_id/id',
                   'location_id/id', 'procure_method', 'route_id/id', 'warehouse_id/id', 'sequence',
                   'group_propagation_option', 'propagate', 'propagate_warehouse_id/id', 'partner_address_id/id',
                   'delay', 'company_id/id'],
        # 'replace': True
        'search_fields': ['picking_type_id', 'location_src_id', 'location_id', 'route_id', 'action', 'company_id']
    }),
    ('uom.category', {
        'fields': ['id', 'name', 'measure_type'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    ('uom.uom', {
        'fields': ['id', 'active', 'name', 'category_id/id', 'uom_type', 'factor_inv', 'factor', 'rounding'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    ('res.currency', {
        'fields': ['id', 'active', 'name', 'currency_unit_label', 'currency_subunit_label', 'symbol', 'position'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    ('res.lang', {
        'fields': ['id', 'active', 'name', 'code', 'iso_code', 'grouping', 'decimal_point', 'thousands_sep',
                   'date_format', 'time_format', 'week_start'],
        'domain': [('active', '=', True)]
        # alle aktiven Sprachen (Beim Laden einer Sprache ist immer der OdooBot-User der write_uid)
    }),
    ('ir.default', {
        'fields': ['id', 'field_id/id', 'user_id', 'json_value', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    ('decimal.precision', {
        'fields': ['id', 'name', 'digits'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    ('fetchmail.server', {  # Das Passwort und der Status werden nicht gespeichert
        'fields': ['id', 'name', 'type', 'server', 'port', 'is_ssl', 'user', 'attach', 'active', 'original', 'priority',
                   'object_id/id']
    }),
    ('ir.mail_server', {
        'fields': ['id', 'name', 'sequence', 'smtp_host', 'smtp_port', 'smtp_debug', 'smtp_encryption', 'smtp_user',
                   'smtp_pass'],
        'domain': [('write_uid', '!=', 1)]  # 1 ist der OdooBot User
    }),
    ('base.automation', {
        'fields': ['id', 'name', 'active', 'model_id/id', 'trigger', 'filter_pre_domain', 'filter_domain', 'state',
                   'code'],
        'domain': [('state', '=', 'code'), ('write_uid', '!=', 1)]  # nur Aktionen mit Python-Code
    }),
    ('ir.ui.view', {
        'fields': ['id', 'name', 'active', 'type', 'model', 'priority', 'mode', 'arch', 'inherit_id/id'],
        'domain': [('name', '!=', 'res.users.groups'), ('write_uid', '!=', 1), ('type', '!=', 'qweb')]
    }),
    ('res.country', {
        'fields': ['id', 'name', 'phone_code', 'code', 'vat_label', 'address_view_id/id', 'address_format',
                   'name_position', 'vat_label'],
        'domain': [('write_uid', '!=', 1)]
    }),
    ('report.paperformat', {
        'fields': ['id', 'name', 'format', 'orientation', 'margin_top', 'margin_bottom', 'margin_left', 'margin_right',
                   'header_line', 'header_spacing', 'dpi'],
        'domain': [('write_uid', '!=', 1)]
    }),
    ('ir.actions.report', {
        'fields': ['id', 'name', 'report_type', 'paperformat_id/id', 'model', 'report_name', 'print_report_name',
                   'multi', 'attachment_use', 'attachment'],
        'domain': [('write_uid', '!=', 1)]
    }),
    ('ir.property', {
        'fields': ['name', 'fields_id/id', 'res_id', 'type', 'value_reference', 'value_float', 'value_integer',
                   'value_text', 'value_binary', 'value_datetime', 'company_id/id'],
        'domain': [('write_uid', '!=', 1), ('res_id', '=', False)],
        # Nur Defaultwerte übernehmen, keine konkreten Daten zu Objekten
        'search_fields': ['fields_id', 'res_id', 'company_id'],
    }),
    ('res.partner.industry', {
        'fields': ['id', 'name', 'full_name', 'active'],
        'domain': [('write_uid', '!=', 1)],
    }),
    ('res.partner.title', {
        'fields': ['id', 'name', 'shortcut'],
        'domain': [('write_uid', '!=', 1)],
    }),
    ('ir.actions.server', {
        'fields': ['id', 'name', 'type', 'usage', 'state', 'sequence', 'model_id/id', 'code', 'child_ids/id',
                   'crud_model_id/id', 'link_field_id/id'],
        'domain': [('write_uid', '!=', 1)],
    }),
    ('ir.server.object.lines', {
        'fields': ['server_id/id', 'col1/id', 'value', 'type'],
        'replace': True,
    }),
    ('ir.cron', {  # TODO: add 'numbercall'
        'fields': ['id', 'cron_name', 'user_id/id', 'active', 'interval_number', 'interval_type', 'doall', 'priority',
                   'ir_actions_server_id/id'],
        'domain': [('write_uid', '!=', 1)],
    }),

])

PRODUCT_MODELS = [
    ('product.pricelist', {
        'fields': ['id', 'name', 'active', 'discount_policy', 'country_group_ids/id', 'sequence', 'company_id/id'],
        'domain': [('write_uid', '!=', 1)]
    }),
    ('product.category', {
        'fields': ['id', 'name', 'parent_id/id', 'property_cost_method', 'property_valuation',
                   'property_account_income_categ_id/id', 'property_account_expense_categ_id/id',
                   'property_account_creditor_price_difference_categ/id', 'property_stock_account_input_categ_id/id',
                   'property_stock_account_output_categ_id/id', 'property_stock_valuation_account_id/id',
                   'removal_strategy_id/id'],
        'domain': [('write_uid', '!=', 1)]
    }),
    ('product.product', { #TODO: image, image_variant
        'fields': ['id', 'name', 'active', 'sale_ok', 'purchase_ok', 'type', 'categ_id/id', 'barcode', 'version',
                   'list_price', 'taxes_id/id', 'standard_price', 'uom_id/id', 'uom_po_id/id', 'description',
                   'invoice_policy', 'expense_policy', 'description_sale', 'supplier_taxes_id/id', 'purchase_method',
                   'description_purchase', 'route_ids/id', 'produce_delay', 'sale_delay', 'tracking',
                   'property_stock_production/id', 'property_stock_inventory/id', 'weight', 'volume', 'landed_cost_ok',
                   'description_pickingout', 'description_pickingin',
                   'property_account_income_id/id', 'property_account_expense_id/id',
                   'property_account_creditor_price_difference/id', 'default_code',
                   'sequence', 'rental', 'company_id/id', 'color'],
        'domain': [('write_uid', '!=', 1)]
    }),
    ('product.pricelist.item', {
        'fields': ['id', 'applied_on', 'product_tmpl_id/id', 'categ_id/id', 'product_id/id', 'min_quantity',
                   'date_start', 'date_end', 'compute_price', 'fixed_price', 'percent_price', 'base', 'price_discount',
                   'price_surcharge', 'price_round', 'price_min_margin', 'price_max_margin', 'base_pricelist_id/id',
                   'pricelist_id/id', 'company_id/id'],
        'replace': True
    }),
    ('stock.warehouse.orderpoint', {
        'fields': ['id', 'name', 'active', 'product_id/id', 'warehouse_id/id', 'product_uom/id', 'location_id/id',
                   'product_min_qty', 'product_max_qty', 'qty_multiple', 'lead_days', 'company_id/id'],
    }),
    # product.template - 'responsible_id/id', 'optional_product_ids/id',
    # product.category - 'property_stock_journal/id'
    # product.template.attribute.line
    # product.attribute.value
    # product.template.attribute.value
    # account.asset.category
    # product.packaging
    # Stücklisten
    # Meldebestände
    # Dateianhänge

]

PARTNER_MODELS = [
    ('res.partner.category', {
        'fields': ['id', 'name', 'color', 'parent_id/id', 'active'],
        'domain': [('write_uid', '!=', 1)]
    }),
    ('res.users', {
        'fields': ['id', 'name', 'active', 'partner_id', 'login', 'signature', 'action_id/id', 'groups_id/id'],
    # todo
        'domain': [('write_uid', '!=', 1)]
    }),
    ('res.partner', { #TODO: image
        'fields': ['id', 'name', 'active', 'is_company', 'title/id', 'parent_id/id', 'ref', 'lang', 'tz', 'user_id/id',
                   'vat', 'website', 'comment', 'category_id/id', 'credit_limit', 'barcode', 'customer', 'supplier',
                   'employee', 'function', 'type', 'street', 'street2', 'zip', 'city', 'country_id/id', 'email',
                   'phone', 'mobile', 'industry_id/id', 'color', 'company_name', 'team_id/id'],
        'domain': [('write_uid', '!=', 1)]
    }),
]

PRODUCT_PARTNER_MODELS = [
    ('product.supplierinfo', {
        'fields': ['id', 'name/id', 'product_name', 'product_code', 'sequence', 'product_uom/id', 'min_qty', 'price',
                   'company_id/id', 'currency_id/id', 'date_start', 'date_end', 'product_id/id', 'product_tmpl_id/id',
                   'delay'],
        'domain': [('write_uid', '!=', 1)]
    }),
]


class DpConfig(models.Model):
    _name = 'dp.config'
    _description = 'Configuration Import/Export'
    _order = 'id desc'

    name = fields.Char(string='Bezeichnung', required=True, readonly=True)
    action = fields.Selection([('import', 'Import'), ('export', 'Export')], 'Aktion', required=True, readonly=True)
    date = fields.Datetime(string="Startdatum", readonly=True, default=lambda *a: fields.Datetime.now())
    date_end = fields.Datetime(string="Enddatum", readonly=True)
    zip_file = fields.Binary('Konfiguration .ZIP file', attachment=True, readonly=True)
    zip_filename = fields.Char('Dateiname', readonly=True)
    log_ids = fields.One2many('dp.config.log', 'config_id', 'Logs', readonly=True)
    detail_ids = fields.One2many('dp.config.detail', 'config_id', 'Details', readonly=True)
    file_cnt = fields.Integer('Anzahl Dateien',
                              help="Gesamtanzahl der Dateien im ZIP-File (ausgenommen 'odoo-config.json')",
                              readonly=True, default=0)
    app_cnt = fields.Integer('Anzahl der Apps', help="Anzahl der installierten Apps (ohne customizations.zip)",
                             readonly=True, default=0)
    export_products = fields.Boolean('Exportiere Produktdaten',
                                     help="Produkte, Kategorien, Preislisten, Lieferantendaten", readonly=True)
    export_partners = fields.Boolean('Exportiere Kontakte',
                                    help="Inkludiert Kunden, Lieferanten und sonstiges Adressen und Kontakte",
                                    readonly=True)
    export_from = fields.Datetime('Export ab', readonly=True,
                                  help='Es werden alle Datensätze mit einem neuerem Erstellungs- oder Änderungsdatum exportiert. Wenn nicht angegeben, so werden alle Datensätze exportiert')

    @api.multi
    def button_reload(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def _get_filename(self, filename):
        return '%s/%s' % (self.path, filename)

    def _create_log(self, name, state, is_error=False):
        vals = {
            'name': name,
            'state': state,
            'config_id': self.id,
            'is_error': is_error,
        }
        self.env['dp.config.log'].sudo().create(vals)

    def _create_detail(self, model, export_cnt=0):

        vals = {
            'name': model,
            'config_id': self.id,
        }
        if self.action == 'import':
            vals['export_cnt'] = export_cnt
        else:
            # Beim Import wird der "total_cnt" später aktualisiert
            vals['total_cnt'] = len(self.env[model].with_context(active_test=False).search([]))
        self.env['dp.config.detail'].sudo().create(vals)

    def _update_details(self):
        # Für jeden Eintrag in den Details (Anzahl der Einträge) wird jetzt nochmals die aktuelle
        # Anzahl ermittelt
        for d in self.sudo().detail_ids:
            d.total_cnt = len(self.env[d.name].with_context(active_test=False).search([]))

    def _export_records(self, model, field_names, domain, sequence=False):
        # Nicht alle Modules haben ein create_date und write_date (zB ir.translation)
        if self.export_from and self.env[model]._fields.get('create_date'):
            domain += ['|', ('create_date', '>=', self.export_from), ('write_date', '>=', self.export_from)]
        records = self.env[model].with_context(active_test=False).search(domain)
        # if hasattr(self.env[model], 'company_id'):
        #    print(model)
        _logger.info('Exporting model %s (%d entries)' % (model, len(records)))
        if records:
            # Feldnamen entfernen, die es in dieser Datenbank nicht gibt.
            # (da zB nicht alle Module installiert sind)
            # Felder wie zB 'payment_id/id' werden geprüft auf 'payment_id'
            filtered_fields = [f for f in field_names if self.env[model]._fields.get(f.split('/')[0], False)]
            if len(filtered_fields) != len(field_names):
                _logger.info('Model %s: Felder wurden entfernt: %s' % (model, set(field_names) - set(filtered_fields)))

            data = records.export_data(filtered_fields, False).get('datas', [])
            raw_data = CSVExport().from_data(filtered_fields, data)

            if sequence:
                filename = "%s_%s" % (sequence, model)
            else:
                filename = model
            filename = self._get_filename('data/' + filename + '.csv')

            with io.open(filename, 'wb') as fp:
                fp.write(raw_data)
            self._create_log(model, TRANS('%d Einträge exportiert') % len(records))

    def _import_records(self, model, filename, search_fields=False):
        abs_filename = self._get_filename('data/' + filename)

        if not os.path.exists(abs_filename):
            return False

        with io.open(abs_filename, 'rb') as fp:
            raw_data = fp.read()

        vals = {
            'res_model': model,
            'file': raw_data,
            'file_name': 'tmp.csv',
            'file_type': 'text/csv',
        }
        import_wiz = self.env['base_import.import'].create(vals)
        options = {'name_create_enabled_fields': {},
                   'separator': ',',
                   'encoding': 'utf-8',
                   'float_decimal_separator': '.',
                   'headers': True,
                   'datetime_format': '',
                   'fields': [],
                   'date_format': '',
                   'advanced': False,
                   'keep_matches': False,
                   'quoting': '"',
                   'float_thousand_separator': ''}

        preview = import_wiz.parse_preview(options)
        # Enthält alle Spalten aus der CSV-Datei
        field_names = preview.get('headers')

        # Das erlaubt die Zuweisung eines inaktiven Eintrags zu einem anderen Objekt (Methode "db_id_for")
        # zB die "picking_type_id" in stock.rule
        context = {
            'active_test': False
        }
        if search_fields:
            context['dp_config_search_fields'] = search_fields
            # Mit diesem Context wird später aus einem create() ein write()
            res = import_wiz.with_context(dp_config_search_fields=search_fields).do(field_names, field_names, options)
        else:
            res = import_wiz.do(field_names, field_names, options)

        if not res.get('messages'):
            # OK-Fall: res = {'ids': [18], 'messages': []}
            file_cnt = len(res.get('ids', []))
            self._create_log(model, TRANS('%d Einträge importiert') % file_cnt)
            return file_cnt
        else:
            # NOK-Fall: res = {'ids': False, 'messages': [{'rows': {'to': 0, 'from': 0}, 'record': 0, 'moreinfo': 'Lösen Sie zunächst die anderen Fehler', 'type': 'error', 'message': "Unbekannter Fehler beim Import: <class 'odoo.exceptions.ValidationError'>: ('Percentages on the Payment Terms lines must be between 0 and 100.', None)"}]}
            self._create_log(model, TRANS('Fehler: %s') % res.get('messages'), is_error=True)
            return False

    def _get_models(self):
        models = OrderedDict()

        models.update(CONFIG_MODELS)
        if self.export_products:  # Füge Produktmodels hinzu
            for m, info in PRODUCT_MODELS:
                models[m] = info
        if self.export_partners:  # Füge Partnermodels hinzu
            for m, info in PARTNER_MODELS:
                models[m] = info
        if self.export_products and self.export_partners:  # Füge gemeinsame Models hinzu
            for m, info in PRODUCT_PARTNER_MODELS:
                models[m] = info
        return models

    def _export_models(self):
        sequence = 1

        for model, model_info in self._get_models().items():
            domain = model_info.get('domain', [])
            if model in self.env:
                field_names = model_info.get('fields')
                self._create_detail(model)
                self._export_records(model, field_names, domain, sequence='%02d' % sequence)
                sequence += 1

    def _import_models(self, force_models=False, exclude_models=[]):
        models = self._get_models()

        # Importiere alle CSV-Dateien im ZIP-File
        for _, _, files in os.walk(self.path + '/data'):
            # Sortiere Dateien nach deren Dateinamen
            files.sort()
            for filename in files:
                if filename[-4:] == '.csv': # e.g. 03_res.partner.bank.csv
                    model = filename[:-4]
                    # Remove sequence ("01_") if exists
                    model = re.sub("^[0-9]*_", "", model)

                    if force_models and model not in force_models:
                        continue
                    if model in exclude_models:
                        continue

                    search_fields = False
                    config = models.get(model)
                    if config:
                        search_fields = config.get('search_fields', False)
                        if config.get('replace', False):
                            # Alle vorhandenen Einträge werden vor dem Import gelöscht
                            to_delete = self.env[model].with_context(active_test=False).search([])
                            self._create_log(model, TRANS('%s Einträge gelöscht') % len(to_delete))
                            to_delete.unlink()
                    _logger.info('Importing file %s' % filename)
                    self._import_records(model, filename, search_fields=search_fields)

    def _export_modules(self):
        installed_modules = self.env['ir.module.module'].search(
            [('state', '=', 'installed'), ('name', '!=', 'studio_customization')])
        module_list = installed_modules.mapped(lambda m: m.name)

        # Enthält die Anzahlt der Einträge pro Objekt
        details = []
        for d in self.detail_ids:
            details.append({
                'model': d.name,
                'export_cnt': d.total_cnt,
            })

        data = {
            'modules': module_list,
            'export_details': details,
        }
        filename = self._get_filename(CONFIG_FILE)
        with open(filename, 'w') as config_file:
            json.dump(data, config_file, indent=4)
        self._create_log('Odoo Apps', TRANS('%d installierte Module') % len(module_list))
        self.app_cnt = len(module_list)

    def _reload_env(self):
        _logger.info("Reloading Environment")
        # Extra Methode wegen pylint wegen "E0203(access-member-before-definition)"
        self.env = self.env()

    def _import_modules(self):
        filename = self._get_filename(CONFIG_FILE)
        with open(filename, 'r') as config_file:
            data = json.load(config_file)

            # Export Details extrahieren
            export_details = data.get('export_details', [])
            for d in export_details:
                self._create_detail(d.get('model', '<unknown>'), d.get('export_cnt', 0))

            # Module installieren
            c_modules = data.get('modules', [])
            domain = [('name', 'in', c_modules), ('state', 'in', ['uninstalled','to install'])]
            modules = self.env['ir.module.module'].search(domain)

            # Log if there is missing a module
            available_modules = [m.name for m in self.env['ir.module.module'].search([('name', 'in', c_modules)])]
            missing_modules = set(c_modules) - set(available_modules)
            if missing_modules:
                self._create_log('Odoo Apps', TRANS('Folgende Module sind nicht verfügbar: %s') % list(missing_modules),
                                 is_error=True)

            if modules:
                self._create_log('Odoo Apps', TRANS('%d Module installiert') % len(modules))
                self.app_cnt = len(modules)
                modules.button_immediate_install()
                # Das Environment muss neu aufgebaut werden, damit die neuen Objekte sichtbar sind
                self.env.reset()
                self._reload_env()

    def _import_company_logo(self):

        filename = self._get_filename(COMPANY_LOGO)
        if not os.path.exists(filename):
            return

        with open(filename, 'rb') as img:
            raw = img.read()
            image_data = base64.b64encode(raw)

        vals = {
            'logo': image_data
        }
        self.env.ref('base.main_company').write(vals)
        self._create_log('Unternehmenslogo', TRANS('importiert'))

    def _export_company_logo(self):
        filename = self._get_filename(COMPANY_LOGO)

        image_data = self.env.ref('base.main_company').logo
        if image_data:
            with open(filename, 'wb') as img:
                img.write(base64.b64decode(image_data))
            self._create_log(TRANS('Unternehmenslogo'), TRANS('exportiert'))
        else:
            self._create_log(TRANS('Unternehmenslogo'), TRANS('nicht vorhanden'), is_error=True)

    def _export_res_config_settings(self):
        ResConfig = self.env['res.config.settings']
        model = 'res.config.settings'
        c = ResConfig.create({})

        fields = Export().get_fields(model)
        field_names = [x['value'] for x in fields if x['value'] not in CONFIG_EXCLUDE_FIELDS]
        self._export_records(model, field_names, domain=[('id', '=', c.id)])

    def _import_res_config_settings(self):
        ResConfig = self.env['res.config.settings']
        model = 'res.config.settings'
        filename = model + '.csv'
        if self._import_records(model, filename):
            # Suche den zuletzt erstellt wizard und führe ihn aus
            c = ResConfig.search([])
            c[-1].execute()

    def _export_studio_customizations(self):

        if not self.env['ir.module.module'].search([('name', '=', 'web_studio'), ('state', '=', 'installed')]):
            return
        # Wenn mindestens eine Anpassung passiert ist, dann Export durchführen
        # ACHTUNG: Sobald das Studiomodul einmal installiert wurde, dann ist dieses Flag nicht mehr gesetzt
        #          und es wird dann auch kein Modul mehr exportiert
        if not self.env['ir.model.data'].search([('studio', '=', True)]):
            return

        # Hier können wir annehmen, dass das Studio-Modul installiert ist und der "import" funktioniert
        from odoo.addons.web_studio.controllers import export

        studio_module = self.env['ir.module.module'].get_studio_module()
        data = self.env['ir.model.data'].search([('studio', '=', True)])
        # content enthält Binärdaten des ZIP-Archivs des "studio_customization"-Moduls
        content = export.generate_archive(studio_module, data)

        filename = self._get_filename(STUDIO_FILE)
        with open(filename, 'wb') as f:
            f.write(content)

    def _import_studio_customizations(self):
        filename = self._get_filename(STUDIO_FILE)

        if os.path.isfile(filename):
            self._create_log('Odoo Studio', TRANS('Importiere customizations.zip'))
            with open(filename, 'rb') as f:
                # Force erzwingt Änderungen auch wenn noupdate=True gesetzt ist
                # Das Verhalten ist dann wie bei einer Modul-Installation
                self.env['ir.module.module'].import_zipfile(f, force=False)

    def _get_path(self, code):
        return '/tmp/%s' % (code)

    def _get_zipfilename(self):
        return '%s.zip' % self.code

    def _update_xmlids(self):

        data = []

        # Ober-Ansichtslager des Warehouse setzen
        if self.env.get('stock.warehouse', False) != False:
            wh = self.env.ref('stock.warehouse0')
            if wh:
                data += [
                    {'xml_id': XMLIDS['warehouse_location_id'], 'record': wh.view_location_id, 'noupdate': True},
                    {'xml_id': XMLIDS['qc_location_id'], 'record': wh.wh_qc_stock_loc_id, 'noupdate': True},
                    {'xml_id': XMLIDS['in_sequence'], 'record': wh.in_type_id.sequence_id, 'noupdate': True},
                    {'xml_id': XMLIDS['out_sequence'], 'record': wh.out_type_id.sequence_id, 'noupdate': True},
                    {'xml_id': XMLIDS['pack_sequence'], 'record': wh.pack_type_id.sequence_id, 'noupdate': True},
                    {'xml_id': XMLIDS['pick_sequence'], 'record': wh.pick_type_id.sequence_id, 'noupdate': True},
                    {'xml_id': XMLIDS['int_sequence'], 'record': wh.int_type_id.sequence_id, 'noupdate': True},
                    {'xml_id': XMLIDS['reception_route'], 'record': wh.reception_route_id, 'noupdate': True},
                    {'xml_id': XMLIDS['delivery_route'], 'record': wh.delivery_route_id, 'noupdate': True},
                    {'xml_id': XMLIDS['crossdock_route'], 'record': wh.crossdock_route_id, 'noupdate': True},
                    {'xml_id': XMLIDS['pick_type'], 'record': wh.pick_type_id, 'noupdate': True},
                    {'xml_id': XMLIDS['pack_type'], 'record': wh.pack_type_id, 'noupdate': True},
                    {'xml_id': XMLIDS['transit_location'],
                     'record': self.env.user.company_id.internal_transit_location_id, 'noupdate': True},

                ]

            # MRP module
            if self.env.get('mrp.production', False) != False:
                data += [
                    {'xml_id': XMLIDS['pbm_type'], 'record': wh.pbm_type_id, 'noupdate': True},
                    {'xml_id': XMLIDS['sam_type'], 'record': wh.sam_type_id, 'noupdate': True},
                    {'xml_id': XMLIDS['manu_type'], 'record': wh.manu_type_id, 'noupdate': True},
                    {'xml_id': XMLIDS['pbm_sequence'], 'record': wh.pbm_type_id.sequence_id, 'noupdate': True},
                    {'xml_id': XMLIDS['sam_sequence'], 'record': wh.sam_type_id.sequence_id, 'noupdate': True},
                    {'xml_id': XMLIDS['manu_sequence'], 'record': wh.manu_type_id.sequence_id, 'noupdate': True},
                    {'xml_id': XMLIDS['sam_loc'], 'record': wh.sam_loc_id, 'noupdate': True},
                    {'xml_id': XMLIDS['pbm_loc'], 'record': wh.pbm_loc_id, 'noupdate': True},
                    # {'xml_id': XMLIDS['pbm_mto_pull_rule'], 'record': wh.pbm_mto_pull_rule, 'noupdate': True},
                    {'xml_id': XMLIDS['pbm_route'], 'record': wh.pbm_route_id, 'noupdate': True},
                ]
        # account module
        if self.env.get('account.account', False) != False:
            for journal_type in ['sale', 'purchase', 'bank', 'cash']:
                j = self.env['account.journal'].search(
                    [('type', '=', journal_type), ('company_id', '=', self.env.user.company_id.id)], limit=1)
                if len(j) == 1:
                    # Achtung: wenn PointOfSale installiert ist, gibt es 2 Journale vom Typ "sale"
                    data += [
                        # Journale und Sequenzen
                        {'xml_id': XMLIDS[journal_type + '_journal'], 'record': j[0], 'noupdate': True},
                        {'xml_id': XMLIDS[journal_type + '_sequence'], 'record': j[0].sequence_id, 'noupdate': True},
                    ]
                    if XMLIDS.get(journal_type + '_account', False):
                        data += [
                            # Default Accounts des Journals
                            {'xml_id': XMLIDS[journal_type + '_account'], 'record': j[0].default_debit_account_id,
                             'noupdate': True},
                        ]

            account = self.env.user.company_id.get_unaffected_earnings_account()
            data += [
                {'xml_id': XMLIDS['unaffected_earnings_account'], 'record': account, 'noupdate': True},
            ]

        # Einträge mit nicht-vorhandenen Datensätzen löschen und protokollieren
        filtered_data = [d for d in data if d['record']]
        if len(filtered_data) != len(data):
            d1 = [d['xml_id'] for d in data]
            d2 = [d['xml_id'] for d in filtered_data]
            _logger.info('XML-IDs setzen: Nicht alle Datensätze waren vorhanden: %s' % (set(d1) - set(d2)))

        # XML-IDS setzen, sofern diese noch nicht existieren
        self.env['ir.model.data']._update_xmlids(filtered_data, update=True)

    def _export_singe_translation(self, lang_code):

        # Erstellen der temporären Tabelle (Achtung: Keyword INHERTITS)
        query = """ CREATE TEMP TABLE tmp_ir_translation_import (
                        imd_model VARCHAR(64),
                        imd_name VARCHAR(128),
                        noupdate BOOLEAN
                    ) INHERITS (ir_translation) """
        self._cr.execute(query)

        # Diese Methode extrahiert alle Übersetzungen aus dem Sourcecode der geladenen Module
        # und speichert diese in einer temporären Tabelle
        # Es handelt sich um den gleichen Aufruf wie "Eine Übersetzung laden"
        # Jede wird weiter hinten der Code von IrTranslationImport ausgetauscht (mittels 'delta_cursor')
        mods = self.env['ir.module.module'].search([('state', '=', 'installed')])
        mods.with_context(overwrite=False, delta_cursor=True)._update_translations(lang_code)

        # self.env['ir.translation'].with_context(delta_cursor=True).load_module_terms(modules, langs)

        # Alle Übersetzungen in ir.translation, die nicht auch in der temporären Tabelle oben vorkommen,
        # werden hier extrahiert und danach exportiert
        # The "only"-keyword guarantees that only value from ir_translation are selected and not from
        # tmp_ir_translation_import (since they are inherited)
        query = """SELECT module,type,name,res_id,src,value,comments FROM ONLY ir_translation i WHERE NOT EXISTS 
                   (SELECT 1 FROM tmp_ir_translation_import t WHERE 
                     i.name=t.name AND
                     lang = lang AND
                     i.src=t.src AND 
                     i.type=t.type AND 
                     i.value = t.value) 
                AND value != src AND value <> '' AND lang='%s'""" % lang_code
        self._cr.execute(query)
        export_terms = self._cr.fetchall()

        filename = self._get_filename('i18n/%s.csv' % lang_code)
        with open(filename, 'wb') as f:
            # Code übernommen aus tools.trans_export (_process)
            writer = pycompat.csv_writer(f, dialect='UNIX')
            writer.writerow(("module", "type", "name", "res_id", "src", "value", "comments"))
            for module, type, name, res_id, src, trad, comments in export_terms:
                writer.writerow((module, type, name, res_id, src, trad, comments))

        self._create_log(TRANS('Übersetzung %s') % lang_code, TRANS('%d Einträge exportiert') % len(export_terms))

        # Drop TEMP Table
        self._cr.execute("DROP TABLE tmp_ir_translation_import")

    def _export_translations(self):

        # Exportiere eine csv-Datei für jede aktive Sprache (zB "i18n/de_DE.csv")
        langs = self.env['res.lang'].search([])
        for lang in langs:
            self._export_singe_translation(lang.code)

    def _import_translations(self):
        for _, _, files in os.walk(self.path + '/i18n'):
            # für jede Datei:
            for filename in files:
                lang_code = filename[:-4]  # Ohne ".csv"

                # Initiales Laden der Sprache sofern noch nicht geladen
                # (Annahme: wenn geladen, dann existieren mehr als 500 Einträge
                languages = self.env['res.lang'].search([('code', '=', lang_code)])
                if len(languages) == 1:
                    trans = self.env['ir.translation'].search([('lang', '=', languages[0].code)])
                    if len(trans) < 500:
                        # Es handelt sich um den gleichen Aufruf wie "Eine Übersetzung laden"
                        mods = self.env['ir.module.module'].search([('state', '=', 'installed')])
                        mods.with_context(overwrite=False)._update_translations(lang_code)
                        self._create_log(TRANS('Übersetzung'), TRANS('Sprache %s geladen') % lang_code)

                # Laden der individuellen Sprachen
                abs_filename = self._get_filename('i18n/' + filename)
                with io.open(abs_filename, 'rb') as fp:
                    raw_data = fp.read()

                vals = {
                    'name': lang_code,
                    'code': lang_code,
                    'data': base64.b64encode(raw_data),
                    'filename': filename,
                    'overwrite': True,
                }
                import_wiz = self.env['base.language.import'].create(vals)
                import_wiz.import_lang()
                self._create_log(TRANS('Übersetzung'), TRANS('Sprache %s importiert') % lang_code)

    def _set_file_cnt(self, path):
        cnt = 0
        for _, _, files in os.walk(path):
            cnt += len(files)
        self.file_cnt = cnt - 1  # Die manifest-Datei "odoo-config.json" wird nicht gezählt

    def set_limits(self):
        # Speichern der ursprünglichen Werte für später
        orig_vals = {}

        for (conf_name, min_value) in CONFIG_LIMITS:
            if tools.config[conf_name] < min_value:
                orig_vals[conf_name] = tools.config[conf_name]
                tools.config[conf_name] = min_value
                _logger.info(
                    "Erhöhe '%s' von %d auf %d" % (conf_name, orig_vals[conf_name], min_value))

        return orig_vals

    def reset_limits(self, orig_vals):
        # Zurücksetzen auf die ursprünglichen Werte
        # Sofern ein Wert geändert wurde, ist der alte Wert in den 'orig_vals' enthalten

        # Zurücksetzen der CPU-Limits
        for conf_name, old_value in orig_vals.items():
            tools.config[conf_name] = old_value
            _logger.info("Reset '%s' auf %d" % (conf_name, old_value))

    def do_import(self):
        self.ensure_one()

        if not self.zip_filename:
            raise UserError(TRANS("Bitte laden Sie eine Konfigurationsdatei hoch."))

        # Schneide die Endung des Dateinamens (".zip") ab
        code = self.zip_filename[:-4]
        self.path = self._get_path(code)

        # ThreadedServer: Wenn limit_time_real + SLEEP_INTERVAL (60s) erreicht ist, dann wird ein reload eingeleitet
        #                 limit_time_cpu hat hier keine Auswirkung
        orig_vals = self.set_limits()

        # Existierendes Verzeichnis löschen (sofern vorhanden)
        shutil.rmtree(self.path, ignore_errors=True)

        # Pfad erstellen und das ZIP-File darin extrahieren
        os.mkdir(self.path)

        zip_data = base64.b64decode(self.zip_file)
        fp = io.BytesIO()
        fp.write(zip_data)
        with ZipFile(fp, 'r') as zip_file:
            zip_file.extractall(self.path)

        self._set_file_cnt(self.path)

        # Muss vor den Modulen importiert werden, da zB das Lager die Sequenznamen auf Basis
        # der Company vergibt.
        self._import_models(['res.company'])

        self._import_modules()
        self._update_xmlids()  # Muss nach den Modulen kommen, da erst dann zB Lagerdaten verfügbar sind
        self._import_res_config_settings()
        # Muss extra importiert werden, da danach ein Reload des Environments notwendig ist
        if self._import_models(['ir.model.fields']):
            self.env.reset()
            self._reload_env()
        self._import_studio_customizations()
        self._import_models(exclude_models=['ir.model.fields', 'res.config.settings'])
        self._import_company_logo()
        self._import_translations()
        self._update_details()

        # Extrahierte Dateien wieder löschen
        shutil.rmtree(self.path)

        self.reset_limits(orig_vals)

        # Enddatum setzen
        self.date_end = fields.Datetime.now()

        return self._history_action(reload=True)

    def get_all_file_paths(self, directory):

        # initializing empty file paths list
        file_paths = []

        # crawling through directory and subdirectories
        for root, _, files in os.walk(directory):
            for filename in files:
                # join the two strings in order to form the full filepath.
                filepath = os.path.join(root, filename)
                file_paths.append(filepath)

        # returning all file paths
        return file_paths

    def do_export(self):
        self.ensure_one()

        self.code = self.name
        self.path = self._get_path(self.code)

        orig_vals = self.set_limits()

        # Existierendes Verzeichnis löschen (sofern vorhanden)
        shutil.rmtree(self.path, ignore_errors=True)

        os.mkdir(self.path)
        os.mkdir(self.path + '/images')
        os.mkdir(self.path + '/data')
        os.mkdir(self.path + '/i18n')

        self._export_translations()

        self._update_xmlids()
        self._export_company_logo()
        self._export_models()
        self._export_res_config_settings()
        self._export_modules()
        self._export_studio_customizations()

        self._set_file_cnt(self.path)

        stream = io.BytesIO()
        # https://www.geeksforgeeks.org/working-zip-files-python/
        with ZipFile(stream, 'w') as zip_file:
            # writing each file one by one
            for filename in self.get_all_file_paths(self.path):
                _logger.info('Export: Zipping file %s' % filename)
                relative_name = filename.replace(self.path, "").strip("/")
                zip_file.write(filename, arcname=relative_name)

        # Temporären Pfad wieder löschen
        shutil.rmtree(self.path)

        self.zip_file = base64.b64encode(stream.getvalue())
        self.zip_filename = self._get_zipfilename()

        self.reset_limits(orig_vals)

        # Enddatum setzen
        self.date_end = fields.Datetime.now()

        return self._history_action()

    def _history_action(self, reload=False):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Import/Export Historie',
            'view_mode': 'form',
            'res_model': 'dp.config',
            'target': 'new',
            'res_id': self.id,
            'context': {'show_reload': reload}
        }


class DpConfigLog(models.Model):
    _name = 'dp.config.log'
    _description = 'Configuration Log'
    _order = 'id'

    name = fields.Char('Bezeichnung', required=True, readonly=True)
    state = fields.Char('Status', required=True, readonly=True)
    config_id = fields.Many2one('dp.config', 'Konfiguration', required=True)
    is_error = fields.Boolean('Fehler')


class DpConfigDetail(models.Model):
    _name = 'dp.config.detail'
    _description = 'Configuration Detail'
    _order = 'id'

    def _compute_is_warn(self):
        for rec in self:
            if rec.config_id.action == 'import' and rec.export_cnt != rec.total_cnt:
                rec.is_warn = True
            else:
                rec.is_warn = False

    name = fields.Char('Model', required=True, readonly=True)
    export_cnt = fields.Integer('Anzahl Export', readonly=True)
    total_cnt = fields.Integer('Aktuelle Anzahl', readonly=True)
    is_warn = fields.Boolean('Warnung', compute='_compute_is_warn')
    config_id = fields.Many2one('dp.config', 'Konfiguration', required=True, readonly=True)
