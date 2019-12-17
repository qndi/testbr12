# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'


    def _default_leave_type_compensation(self):
        return self.env.ref('hr_holidays.holiday_status_comp')


    def _default_leave_type_sickness(self):
        return self.env.ref('hr_holidays.holiday_status_sl')


    leave_type_vacation = fields.Many2one('hr.leave.type', 'Abwesenheitstyp Urlaub')
    leave_type_compensation = fields.Many2one('hr.leave.type', 'Abwesenheitstyp Zeitausgleich',
        default=_default_leave_type_compensation)
    leave_type_sickness = fields.Many2one('hr.leave.type', 'Abwesenheitstyp Krankenstand',
        default=_default_leave_type_sickness)
    leave_type_public_holiday = fields.Many2one('hr.leave.type', 'Abwesenheitstyp Feiertag')


    @api.model
    def dp_hr_postinstall(self):
        # Set the default leave types. We can't set them via a default
        # function since the records don't yet exist when the default
        # function is called during the installation of the module.
        # Allowing self.env.ref() to return None would be enough to allow
        # installation, but the field would remain empty.
        vals = {
            'leave_type_vacation': self.env.ref('dp_hr.leave_type_vacation').id,
            'leave_type_public_holiday': self.env.ref('dp_hr.leave_type_public_holiday').id,
        }
        self.env.user.company_id.write(vals)

        # Make unused leave types inactive
        def set_inactive(xmlid):
            obj = self.env.ref(xmlid, False)
            if obj and obj.active:
                obj.active = False


        set_inactive('hr_holidays.holiday_status_cl')
        set_inactive('hr_holidays.holiday_status_unpaid')
