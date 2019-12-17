# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import models, fields


class Company(models.Model):
    _inherit = 'res.company'

    send_invoice = fields.Boolean(string=u'Ausdruck mit der E-Rechnung mitschicken',
                                  help=u'Wenn dieses Feld gesetzt ist, wird ein Ausdruck der Rechnung mit der '
                                       u'E-Rechnung mitgeschickt')
