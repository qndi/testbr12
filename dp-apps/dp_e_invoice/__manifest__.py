# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).


{
    'name': 'datenpol E-Rechnung',
    'summary': 'Modul zum Einreichen von Rechnungen über den ebInterface Rechnungsstandard',
    'category': 'Accounting & Finance',
    'license': 'OPL-1',
    'version': '12.0.1.0.0',
    'author': 'datenpol GmbH',
    'support': 'office@datenpol.at',
    'website': 'http://www.datenpol.at',
    'depends': [
        'account',
        'sale'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/assets_backend.xml',
        'views/account_invoice_view.xml',
        'views/res_partner_view.xml',
        'views/res_partner_bank_view.xml',
        'views/eb_group_view.xml',
        'views/res_company_view.xml',
        'data/config_parameter.xml',
        'wizard/e_invoice_wizard_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}
