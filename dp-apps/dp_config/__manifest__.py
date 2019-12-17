# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': 'dp Configuration Management',
    'summary' : 'datenpol Configuration Management',
    'version': '12.0.1.0.0',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'support': 'office@datenpol.at',
    'website': 'https://www.datenpol.at',
    'depends': ['base_import'],
    'data': [
        'security/ir.model.access.csv',
        'views/dp_config.xml',
        'wizards/dp_config.xml',
    ],
    'images': [
        'static/description/Banner.jpg'
    ],
    'installable': True,
    'auto_install': False,
}


#TODO notes
# Config soll öfters importierbar sein

#US1:
# - Konfig kann initial von einem Template (zB "Fertigung") genommen werden
# - danach wird diese immer wieder angepasst
# - PROD: die Datenbank wir neu angelegt und die Konfig wird eingespielt
#
#US2:
# - Konfig kann initial von einem Template (zB "Fertigung") genommen werden
# - danach wird diese immer wieder angepasst
# - PROD: die Konfig wird in der bestehenden Datenbank mehrmals eingespielt
#
#US3:
# - Konfig kann initial von einem Template (zB "Fertigung") genommen werden
# - danach wird diese immer wieder angepasst
# - PROD: die Konfig wird in der bestehenden Datenbank mehrmals eingespielt
# - PROD: es werden Konfigurationen verändert
# - TEST: es wird die Konfig der PROD in die TEST eingespielt
# - TEST: es wird wieder in der TEST geändert
# - PROD: Änderungen werden wieder in die PROD eingespielt
