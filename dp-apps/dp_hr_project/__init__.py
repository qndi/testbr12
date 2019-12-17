# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from . import models


# noinspection PyUnusedLocal
def post_init(cr, registry):
    # Don't book vacation or compensation time on a project. This completes
    # the other part in the model.
    # The timesheet_generate boolean is only for the UI, the other two fields
    # determine whether the booking happens or not. They're set by an
    # onchange on the boolean field.
    # Odoo has already filled out all the fields by the time our modification
    # becomes effective, thus we revert that.
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    leave_types = env['hr.leave.type'].with_context(active_test=False).search([])
    vals = {
        'timesheet_generate': False,
        'timesheet_project_id': False,
        'timesheet_task_id': False,
    }
    leave_types.write(vals)
