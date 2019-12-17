# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

# noinspection PyStatementEffect
{
    'name': """DP EU-GDPR""",
    'summary': """General Data Protection Regulation""",
    'description': """DSGVO, EU-DSGVO, GDPR, EU-GDPR, General Data Protection Regulation, Dateschutzgrundverordnung, Datenschutz-Grundverordnung, RGPD, Règlement général sur la protection des données, Right of Access, Right to rectification, Right to erasure, Right to restriction of processing, Right to data portability, Right to object""",
    'category': 'Extra Tools',
    'version': '12.0.1.0.0',
    'license': 'OPL-1',
    'author': 'datenpol gmbh',
    'support': 'office@datenpol.at',
    'website': 'https://www.datenpol.at/',
    'depends': [
        'base',
        'mail_bot',
        'document',
    ],
    'data': [
        'data/sequence.xml',
        'data/assets.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/menuitem.xml',
        'views/gdpr_custom.xml',
    ],
    'images': ['static/description/Banner.jpg'],
    'installable': True,
    'auto_install': False,
    'application': True,
}
