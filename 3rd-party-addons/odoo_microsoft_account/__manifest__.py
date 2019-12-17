# See LICENSE file for full copyright and licensing details.

{
    'name': 'Microsoft Users - Odoo Integration Base Module',
    'version': '12.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Extra Tools',
    'author': 'Serpent Consulting Services Pvt. Ltd.',
    'website': 'https://www.serpentcs.com',
    'depends': ['auth_oauth'],
    'data': [
        'views/res_config.xml',
        'views/oauth_provider.xml',
        'data/auth_oauth_data.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'price': 129,
    'currency': 'EUR'
}
