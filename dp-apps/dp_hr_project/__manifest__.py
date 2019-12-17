# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'Erweiterung für Projektzeiten',
    'category': 'HR',
    'description': """
        offen""",
    'version': '12.0.1.0.0',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'website': 'https://www.datenpol.at/',
    'depends': [
        'dp_hr',
        'sale_timesheet',
    ],
    'data': [
        'views/dp_timesheet_views.xml',
        'views/project_views.xml',
        'views/res_company_views.xml',
        'reports/dp_timesheet_templates.xml',
        'security/ir.model.access.csv',
        'security/security.xml',
    ],
    'installable': True,
    'auto_install': False,
    'demo': [
        'data/dp_hr_project_demo.xml',
    ],
    'post_init_hook': 'post_init',
}
