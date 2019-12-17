# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import logging
from odoo import api, models
from odoo.addons.base.models.ir_translation import IrTranslationImport

_logger = logging.getLogger(__name__)


class DeltaIrTranslationExport(IrTranslationImport):
    """This is a copy of IrTranslationImport with some modifications."""

    _table = 'tmp_ir_translation_import'

    def __init__(self, model):

        self._cr = model._cr
        self._model_table = model._table
        self._overwrite = model._context.get('overwrite', False)
        self._debug = False
        self._rows = []

        # No Table creation here => it is done in dp_config

    def finish(self):
        """ Transfer the data from the temp table to ir.translation """
        cr = self._cr


        # Step 0: insert rows in batch
        query = """ INSERT INTO %s (name, lang, res_id, src, type, imd_model,
                                    module, imd_name, value, state, comments)
                    VALUES """ % self._table
        for rows in cr.split_for_in_conditions(self._rows):
            cr.execute(query + ", ".join(["%s"] * len(rows)), rows)

        _logger.debug("ir.translation.cursor: We have %d entries to process", len(self._rows))

        # Step 1: resolve ir.model.data references to res_ids
        cr.execute(""" UPDATE %s AS ti
                          SET res_id = imd.res_id,
                              noupdate = imd.noupdate
                       FROM ir_model_data AS imd
                       WHERE ti.res_id IS NULL
                       AND ti.module IS NOT NULL AND ti.imd_name IS NOT NULL
                       AND ti.module = imd.module AND ti.imd_name = imd.name
                       AND ti.imd_model = imd.model; """ % self._table)

        # Records w/o res_id must _not_ be inserted into our db, because they are
        # referencing non-existent data.
        cr.execute("DELETE FROM %s WHERE res_id IS NULL AND module IS NOT NULL" % self._table)

        self._rows.clear()
        return True

class IrTranslation(models.Model):
    _inherit = 'ir.translation'

    @api.model
    def _get_import_cursor(self):
        if self.env.context.get('delta_cursor', False):
            # If this routine is called from dp_config, then use this cursor
            return DeltaIrTranslationExport(self)
        else:
            # Original return
            return IrTranslationImport(self)
