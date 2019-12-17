# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'Dp Bmd Export',
    'summary' : 'Exports customer and invoices for BMD',
    'version': '12.0.0.0.0',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'support': 'office@datenpol.at',
    'website': 'https://www.datenpol.at',
    'depends': [
        'account',
        'account_accountant',
        'l10n_at',
        'document',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/account_tax_data.xml',
        'views/bmd_export.xml',
        'views/account_invoice.xml',
        'views/account_tax.xml',
        'views/res_partner.xml',
        'wizards/bmd_export_wizard.xml',
        'views/menuitems.xml',
    ],
    'images': [
        'static/description/Banner.jpg'
    ],
    'installable': True,
    'auto_install': False,
}
