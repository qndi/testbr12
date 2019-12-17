# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'Dp Vat Check',
    'summary': '2-stufige UID Prüfung',
    'version': '12.0.1.0.3',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'support': 'office@datenpol.at',
    'website': 'https://www.datenpol.at',
    'depends': [
    ],
    'data': [
        'views/res_partner.xml',
        'data/config_parameter.xml'
    ],
    'images': [
        'static/description/Banner.jpg'
    ],
    'installable': True,
    'auto_install': False,
}
