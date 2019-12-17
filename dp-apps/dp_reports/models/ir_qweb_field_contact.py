# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _


class IrQwebFieldContact(models.AbstractModel):
    _inherit = 'ir.qweb.field.contact'


    @api.model
    def get_available_options(self):
        options = super(IrQwebFieldContact, self).get_available_options()
        options.get('fields',{}).get('params',{}).get('params',{}).append('absender')

        return options