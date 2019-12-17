# Copyright 2018-Today datenpol gmbh(<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'datepol Vorlage blau',
    'category': 'Reports',
    'version': '12.0.1.0.0',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'website': 'https://www.datenpol.at',
    'summary': """Datenpol Vorlage 'Blau'""",
    'description': """Datenpol Vorlage 'Blau'""",
    'depends': [
        'web'
    ],
    'data': [
        'views/res_company.xml',
        'reports/report_templates.xml',
        'data/report_layout.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
}
