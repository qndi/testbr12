# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'datenpol Elasticsearch',
    'summary': 'Generic Elastic Search Module',
    'version': '12.0.0.0.0',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'support': 'office@datenpol.at',
    'website': 'https://www.datenpol.at',
    'depends': [
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_jobs.xml',
    ],
    'images': [
        'static/description/Banner.jpg'
    ],
    'external_dependencies': {'python': ['elasticsearch', 'certifi']},
    'installable': True,
    'auto_install': False,
}
