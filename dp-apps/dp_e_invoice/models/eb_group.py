# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import models, fields


class eb_group(models.Model):
    _name = 'eb.group'

    name = fields.Char(string='Bezeichnung', required=True)
    content = fields.Char(string='Inhalt', required=True)
    active = fields.Boolean(string='Aktiv', default=True)
