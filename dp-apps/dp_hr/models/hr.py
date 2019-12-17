# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .. import dp_tools


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'


    is_travel_time = fields.Boolean('Reisezeit', help='Hiermit wird diese '
        'Zeitbuchung als "Reisezeit" gekennzeichnet. Reisezeit zählt als '
        'normale Anwesenheit, wird jedoch bei den Überstunden und allfälligen '
        'Warnungen nicht berücksichtigt.')


    @api.constrains('check_in', 'check_out')
    def _check_same_day(self):
        for record in self:
            if not record.check_out:
                continue

            # We rely on the condition that every attendance is contained
            # within one day, as seen in the timezone GMT+1
            check_in_gmt1 = dp_tools.convert_datetime_gmt1(record.check_in)
            check_out_gmt1 = dp_tools.convert_datetime_gmt1(record.check_out)
            if check_in_gmt1.date() != check_out_gmt1.date():
                raise ValidationError(_('Die Anwesenheit muss vollständig '
                    'innerhalb eines Tages liegen.'))


    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        DpTimesheetDay = self.env['dp.timesheet.day']

        for record in res:
            DpTimesheetDay.recalculate_affected(record.employee_id,
                record.check_in, record.check_out)

        return res


    def write(self, vals):
        DpTimesheetDay = self.env['dp.timesheet.day']

        affected_periods = []

        for record in self:
            affected_periods.append((record.employee_id, record.check_in,
                record.check_out))

        res = super().write(vals)

        for ap in affected_periods:
            DpTimesheetDay.recalculate_affected(*ap)

        for record in self:
            DpTimesheetDay.recalculate_affected(record.employee_id,
                record.check_in, record.check_out)

        return res


    def unlink(self):
        affected_periods = []

        for record in self:
            affected_periods.append((record.employee_id, record.check_in,
                record.check_out))

        res = super().unlink()

        for ap in affected_periods:
            self.env['dp.timesheet.day'].recalculate_affected(*ap)

        return res


    @api.model
    def on_install(self):
        # This is called while installing the module to fix the read
        # permissions so that unprivileged users can only see their own
        # attendances.
        # This can't be done via XML since the record is noupdate. It can't
        # be done in config's data_updates since app store customers don't
        # have that.
        perm = self.env.ref('hr_attendance.hr_attendance_rule_attendance_employee')
        perm.perm_read = True


class HrLeave(models.Model):
    _inherit = 'hr.leave'


    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Determine the default leave type by the type of leaves which are
        # shown
        if 'holiday_status_id' in fields_list:
            company = self.env['dp.timesheet'].get_company()
            type_map = {
                'only_vacations': company.leave_type_vacation.id,
                'only_sicknesses': company.leave_type_sickness.id,
                'only_public_holidays': company.leave_type_public_holiday.id,
            }
            for key in type_map:
                if key in self.env.context:
                    res['holiday_status_id'] = type_map[key]
                    # Since only one of the modes is active at once we can
                    # stop now
                    break

        return res


    def name_get(self):
        res = []

        # Use a different name than Odoo does, thus there's no super() call
        for record in self:
            res.append((record.id, record.name))

        return res


    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        try:
            company = self.env['dp.timesheet'].get_company()
        except UserError:
            # Make the module installable. During installation the values
            # for the computed fields are computed which involves a search.
            # Since the leave types aren't assigned yet this fails. They'll
            # be assigned by res.company,dp_hr_postinstall() later.
            # That means there are errors in the log that the NOT NULL
            # constraints on these colums can't be set while they are NULL.
            # The constraints will appear on the next update after setting
            # the fields.
            # While the fields are unset the resulting domain is too broad.
            return super().search(args, offset, limit, order, count)

        context = self.env.context

        args = args.copy()

        if 'only_vacations' in context:
            args.append(('holiday_status_id', 'in', [
                company.leave_type_vacation.id,
                company.leave_type_compensation.id,
            ]))
        elif 'only_sicknesses' in context:
            args.append(('holiday_status_id', '=', company.leave_type_sickness.id))
        elif 'only_public_holidays' in context:
            args.append(('holiday_status_id', '=', company.leave_type_public_holiday.id))

        return super().search(args, offset, limit, order, count)


    @api.constrains('date_from', 'date_to')
    def _check_date(self):
        for leave in self:
            domain = [
                ('employee_id', '=', leave.employee_id.id),
                ('date_from', '<=', leave.date_to),
                ('date_to', '>=', leave.date_from),
                ('holiday_status_id', '=', leave.holiday_status_id.id),
                ('state', 'not in', ['cancel', 'refuse']),
                ('id', '!=', leave.id),
            ]
            conflicting_leaves = self.search(domain)
            if conflicting_leaves:
                msg = _('Es können keine sich überschneidende Abwesenheiten '
                    'für dieselbe Person eingetragen werden. Bereits vorhanden '
                    'sind: %s')
                msg %= ', '.join(['%s - %s' % (cl.date_from, cl.date_to) for cl in conflicting_leaves])
                raise ValidationError(msg)


    @api.onchange('holiday_status_id')
    def _onchange_holiday_status_id(self):
        if self.holiday_status_id:
            self.name = self.holiday_status_id.name


    @api.model
    def create(self, vals):
        res = super().create(vals)

        self.env['dp.timesheet.day'].recalculate_affected(res.employee_id,
            res.date_from, res.date_to)

        return res


    def write(self, vals):
        DpTimesheetDay = self.env['dp.timesheet.day']

        affected_periods = []

        for record in self:
            affected_periods.append((record.employee_id, record.date_from,
                record.date_to))

        res = super().write(vals)

        for ap in affected_periods:
            DpTimesheetDay.recalculate_affected(*ap)

        for record in self:
            DpTimesheetDay.recalculate_affected(record.employee_id,
                record.date_from, record.date_to)

        return res


    def unlink(self):
        affected_periods = []

        for record in self:
            affected_periods.append((record.employee_id, record.date_from,
                record.date_to))

        res = super().unlink()

        for ap in affected_periods:
            self.env['dp.timesheet.day'].recalculate_affected(*ap)

        return res


class HrLeaveAllocation(models.Model):
    _inherit = 'hr.leave.allocation'
    _sql_constraints = [
        # Odoo disallows negative durations, but we want them
        ('duration_check', 'CHECK(1=1)', ''),
    ]


    # It would make sense to make this field required, but then the Odoo demo
    # data would create problems since it doesn't specify this value
    date_effective = fields.Date('Stichtag')


    def action_open_leave_allocation(self):
        company = self.env['dp.timesheet'].get_company()

        action = self.env.ref('hr_holidays.hr_leave_allocation_action_all').read()[0]
        context = {
            'default_holiday_status_id': company.leave_type_vacation.id,
            'search_default_my_leaves': 1,
            'needaction_menu_ref': ['hr_holidays.menu_open_company_allocation'],
        }
        action['context'] = context

        return action


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'


    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        # Overriding the regular search() doesn't result into the desired
        # limitation of the offered leave types in the vacation view.
        # The superclass also overrides this special method, that may be part
        # of the reason why this is necessary.

        args = args.copy()
        company = self.env['dp.timesheet'].get_company()

        if 'limit_leave_types' in self.env.context:
            args.append(('id', 'in', [
                company.leave_type_vacation.id,
                company.leave_type_compensation.id,
            ]))

        return super()._search(args, offset, limit, order, count, access_rights_uid)


class HrContract(models.Model):
    _inherit = 'hr.contract'


    @api.constrains('employee_id', 'date_start', 'date_end')
    def _check_overlap(self):
        for contract in self:
            # The SQL OVERLAPS expression uses the half-open interval
            # start <= time < end, thus two periods with only an endpoint
            # in common do not overlap. Since we don't allow that condition
            # the dates must be shifted in order to archive the desired
            # behaviour.
            query = """
                SELECT 1
                  FROM hr_contract
                 WHERE (DATE %s, DATE %s) OVERLAPS (date_start, COALESCE(date_end, DATE %s))
                   AND employee_id = %s
                   AND id != %s
            """

            # Left overlap
            date_start = contract.date_start - datetime.timedelta(days=1)
            date_end = contract.adapt_date(contract.date_end)
            self.env.cr.execute(query, (date_start, date_end,
                datetime.date.max, contract.employee_id.id, contract.id))
            left_overlap = self.env.cr.fetchall()

            # Right overlap
            date_end = contract.adapt_date(contract.date_end)
            try:
                date_end += datetime.timedelta(days=1)
            except OverflowError:
                # In case the contract has no end date then date_end will
                # be datetime.date.max in order to calculate open-end.
                # Since this is already the maximum value we can't add
                # anything and it wouldn't make a difference.
                pass
            self.env.cr.execute(query, (contract.date_start, date_end,
                datetime.date.max, contract.employee_id.id, contract.id))
            right_overlap = self.env.cr.fetchall()

            if left_overlap or right_overlap:
                raise ValidationError(_('Vertragslaufzeiten dürfen sich nicht überschneiden.'))


    @api.model
    def create(self, vals):
        res = super().create(vals)

        self.env['dp.timesheet.day'].recalculate_affected(res.employee_id,
            res.date_start, self.adapt_date(res.date_end))

        return res


    def write(self, vals):
        DpTimesheetDay = self.env['dp.timesheet.day']

        affected_periods = []
        date_start = fields.Date.to_date(vals.get('date_start'))
        date_end = fields.Date.to_date(vals.get('date_end'))

        for record in self:
            if date_start and (record.date_start < date_start):
                affected_periods.append((record.employee_id, record.date_start,
                    date_start))

            if date_start and (record.date_start > date_start):
                affected_periods.append((record.employee_id, date_start,
                    record.date_start))

            if date_end and record.date_end and (record.date_end > date_end):
                affected_periods.append((record.employee_id, date_end,
                    record.date_end))

            if date_end and (not record.date_end) and (self.adapt_date(record.date_end) > date_end):
                affected_periods.append((record.employee_id, date_end,
                    self.adapt_date(record.date_end)))

        res = super().write(vals)

        for ap in affected_periods:
            DpTimesheetDay.recalculate_affected(*ap)

        return res


    def unlink(self):
        affected_periods = []

        for record in self:
            affected_periods.append((record.employee_id, record.date_start,
                self.adapt_date(record.date_end)))

        res = super().unlink()

        for ap in affected_periods:
            self.env['dp.timesheet.day'].recalculate_affected(*ap)

        return res


    def adapt_date(self, date):
        # In case no date_end is set we have to recalculate open-end
        if date:
            return date

        return datetime.date.max


class HrEmployee(models.Model):
    _inherit = 'hr.employee'


    show_leaves = fields.Boolean('Able to see Remaining Leaves', compute='_compute_show_leaves')


    def _compute_show_leaves(self):
        for record in self:
            record.show_leaves = False


    @api.model
    def create(self, vals):
        res = super().create(vals)

        domain = [
            ('apply_to_new_employees', '=', True),
        ]
        template = self.env['dp.leave.template'].search(domain, limit=1)
        if template:
            vals = {
                'template_id': template.id,
                'employee_ids': [(4, res.id, 0)],
            }
            wizard = self.env['dp.leave.template.import'].create(vals)
            wizard.do_import()

        return res


    def action_open_timereports(self):
        action = self.env.ref('dp_hr.dp_timesheet_action').read()[0]
        action['domain'] = [('employee_id', '=', self.id)]
        return action
