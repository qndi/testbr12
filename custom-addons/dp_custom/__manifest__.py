# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'Dp Custom',
    'summary': '',
    'version': '12.0.1.0.14',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'support': 'office@datenpol.at',
    'website': 'https://www.datenpol.at',
    'depends': [
        'queue_job',
        'sale_subscription'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
        'views/res_partner.xml',
        'views/res_company.xml',
        'views/efr_location.xml',
        'views/efr_cash_register.xml',
        'views/efr_transactions.xml',
        'views/sale_subscription.xml',
        'views/efr_invoice_term.xml',
        'views/account_invoice.xml',
        'wizards/sale_subscription_subsequent.xml',
        'wizards/sale_subscription_normal_billing.xml',
    ],
    'images': [
        'static/description/Banner.jpg'
    ],
    'installable': True,
    'auto_install': False,
}
