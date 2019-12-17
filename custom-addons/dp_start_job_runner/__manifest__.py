# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'Dp Start Job Runner',
    'summary': 'Enables Queue Job Runner on Odoo.sh',
    'version': '12.0.1.0.0',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'support': 'office@datenpol.at',
    'website': 'https://www.datenpol.at',
    'depends': [
        'queue_job',
    ],
    'data': [
    ],
    'images': [
        'static/description/Banner.jpg'
    ],
    'installable': True,
    'auto_install': False,
}
