# -*- coding: utf-8 -*-
from odoo import models, api, _


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.multi
    def unlink(self):
        if self.env.context.get('unlink_index', False):
            return super(IrAttachment, self).unlink()

        # wenn einzelne Dokumente gelöscht werden, nicht der gesamte Index, schreibe Index neu
        to_delete = {}
        for record in self:
            # ids der zugehörigen Models zwischenspeichern
            to_delete[record.res_model] = to_delete.get(record.res_model, []) + [record.res_id]

        # Attachments tatsächlich löschen, damit sie nicht erneut indiziert werden
        res = super(IrAttachment, self).unlink()

        # Index neu indizieren, ohne gelöschte Attachments
        for model in to_delete:
            if hasattr(self.env[model], '_elastic_index_attachments'):
                if self.env[model]._elastic_index_attachments:
                    self.env[model].browse(set(to_delete[model])).index()

        return res

    def _inverse_datas(self):
        # Add document to index on elasticsearch server
        # -> in this method, because _index method would not always call overridden method

        super(IrAttachment, self)._inverse_datas()
        for record in self:
            if record.res_model and hasattr(self.env[record.res_model], '_elastic_index_attachments'):
                if self.env[record.res_model]._elastic_index_attachments:
                    self.env[record.res_model].browse(record.res_id).index()
