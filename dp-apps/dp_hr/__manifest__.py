# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'dp Time Report',
    'summary': '',

    'description': """
        offen
    """,

    'author': 'datenpol gmbh',
    'website': 'https://www.datenpol.at/',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Human Resources',
    'version': '12.0.1.0.0',
    'license': 'OPL-1',

    # Any module necessary for this one to work correctly
    'depends': [
        'decimal_precision',
        'hr_attendance',
        'hr_holidays',
        'hr_contract',
    ],

    # Always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/hr_data.xml',
        'data/hr_data_noupdate.xml',
        'views/dp_views.xml',
        'views/hr_views.xml',
        'views/res_views.xml',
        'views/menus.xml',
        'wizards/wizard_hr_break.xml',
        'wizards/dp_leave_template_import_views.xml',
        'reports/dp_timesheet_templates.xml',
    ],

    # Only loaded in demonstration mode
    'demo': [
        'data/dp_hr_demo.xml',
    ],

    'application': True,
}
