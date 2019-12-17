# Copyright 2018-Today datenpol gmbh(<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'datepol Report-Anpassungen',
    'category': 'Custom',
    'version': '12.0.0.0.0',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'website': 'https://www.datenpol.at',
    'summary': """Individuelle Report Anpassungen""",
    'description': """Individuelle Report Anpassungen""",
    'depends': [
        'base',
        'web'
    ],
    'data': [
        'reports/report_templates.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
}
