# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model
    def create(self, values):
        res = super(MailMessage, self).create(values)
        if res.message_type != 'notification':
            if res.model and hasattr(self.env[res.model], '_elastic_index_message'):
                if self.env[res.model]._elastic_index_message:
                        self.env[res.model].browse(res.res_id).index()
        return res
