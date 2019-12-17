# Copyright 2018-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons import decimal_precision as dp
from odoo.tools import float_compare

from .. import dp_tools


class DpTimesheet(models.Model):
    _name = 'dp.timesheet'
    _inherit = 'mail.thread'
    _description = 'Time Report'
    # Do not change this, calculations rely on this order
    _order = 'date_from DESC, id DESC'
    _sql_constraints = [
        ('e_d_unique', 'UNIQUE (employee_id, date_from)', 'Der Mitarbeiter hat bereits einen Time Report mit diesem Startdatum.'),
    ]


    def name_get(self):
        res = []

        for record in self:
            name = '%s %s - %s' % (record.employee_id.name,
                dp_tools.format_date(record.date_from),
                dp_tools.format_date(record.date_to))
            res.append((record.id, name))

        return res

    state_values = [
        ('open', 'Offen'),
        ('awaiting_approval', 'Erwarte Genehmigung'),
        ('approved', 'Genehmigt'),
    ]

    def get_carryover_domain(self, record):
        return [
            ('employee_id', '=', record.employee_id.id),
            ('state', '=', 'approved'),
            ('date_from', '<', record.date_from),
        ]

    in_days = 'In Tagen'
    timesheet_scope_prev = 'Inkludiert alle vorigen genehmigten Time Reports. Dieses Time Report sowie die folgenden sind nicht berücksichtigt.'
    timesheet_scope_post = 'Inkludiert alle vorigen genehmigten Time Reports und dieses. Die folgenden Time Reports sind nicht berücksichtigt.'


    state = fields.Selection(state_values, 'Status Time Report', default='open', track_visibility='onchange')
    employee_id = fields.Many2one('hr.employee', 'Mitarbeiter', required=True)
    date_from = fields.Date('Von', required=True)
    date_to = fields.Date('Bis', required=True)
    day_ids = fields.One2many('dp.timesheet.day', 'timesheet_id', 'Tage')
    attendance_planned = fields.Float('Geplante Anwesenheit', compute='_compute_timesheet',
        store=True, digits=dp.get_precision('HR Time'),
        help='Urlaube, Krankenstände, Feiertage und sonstige Abwesenheiten werden nicht zur geplanten Anwesenheit gezählt.')
    attendance_actual = fields.Float('Tatsächliche Anwesenheit', compute='_compute_timesheet', store=True,
        digits=dp.get_precision('HR Time'))
    compensation_spent = fields.Integer('Zeitausgleich', compute='_compute_timesheet', store=True, help=in_days)
    travel_time = fields.Float('Reisezeit', compute='_compute_timesheet', store=True,
        digits=dp.get_precision('HR Time'))
    overtime_actual = fields.Float('Mehrstunden', compute='_compute_timesheet', store=True,
        digits=dp.get_precision('HR Time'))
    vacation_spent = fields.Integer('Konsumierter Urlaub', compute='_compute_timesheet', store=True, help=in_days)
    sickness_spent = fields.Integer('Krankenstand', compute='_compute_timesheet', store=True, help=in_days)
    others_spent = fields.Integer('Sonstiges', compute='_compute_timesheet', store=True,
        help=in_days + '. Unter Sonstiges werden Feiertage verstanden.')
    vacation_carryover = fields.Integer('Urlaubsübertrag', compute='_compute_vacation_carryover',
        help=in_days + '. ' + timesheet_scope_prev)
    vacation_new = fields.Integer('Urlaubszuschreibung', readonly=True, help=in_days)
    vacation_total = fields.Integer('Gesamter Urlaubsanspruch', compute='_compute_vacation_total',
        help=in_days + '. ' + timesheet_scope_post)
    vacation_merged = fields.Float('Kombinierter Urlaub', compute='_compute_vacation_merged', store=True)
    overtime_carryover = fields.Float('Mehrstundenübertrag', compute='_compute_overtime_carryover',
        help=timesheet_scope_prev, digits=dp.get_precision('HR Time'))
    overtime_correction = fields.Float('Mehrstundenkorrekturen', digits=dp.get_precision('HR Time'),
        readonly=True)
    # The space at the end of the string silences the warning about fields with identical names
    overtime_correction_ids = fields.One2many('dp.overtime', string='Mehrstundenkorrekturen ', compute='_compute_overtime_correction_ids')
    overtime_total = fields.Float('Gesamte Mehrstunden', compute='_compute_overtime_total',
        help=in_days + '. ' + timesheet_scope_post, digits=dp.get_precision('HR Time'))
    overtime_merged = fields.Float('Kombinierte Mehrstunden', compute='_compute_overtime_merged', store=True)
    manager_id = fields.Many2one('res.users', 'Manager', related='employee_id.parent_id.user_id', readonly=True)
    user_id = fields.Many2one('res.users', 'Benutzer', related='employee_id.user_id', readonly=True)
    date_effective_carryover = fields.Date('Stichtag', compute='_compute_date_effective_carryover')
    vacation_spent_in_hours = fields.Float('Konsumierter Urlaub in Stunden', compute='_compute_timesheet_in_hours',
        digits=dp.get_precision('HR Time'))
    sickness_spent_in_hours = fields.Float('Krankenstand in Stunden', compute='_compute_timesheet_in_hours',
        digits=dp.get_precision('HR Time'))
    others_spent_in_hours = fields.Float('Sonstiges in Stunden', compute='_compute_timesheet_in_hours',
      digits=dp.get_precision('HR Time'))


    @api.depends('day_ids', 'day_ids.attendance_planned',
        'day_ids.attendance_actual', 'day_ids.compensation_spent',
        'day_ids.travel_time', 'day_ids.overtime_actual',
        'day_ids.vacation_spent', 'day_ids.sickness_spent',
        'day_ids.others_spent')
    def _compute_timesheet(self):
        for record in self:
            sums = {
                'attendance_actual': 0.0,
                'travel_time': 0.0,
                'vacation_spent': 0,
                'sickness_spent': 0,
                'others_spent': 0,
                'compensation_spent': 0,
            }

            # Calculate these values only up to the current date
            accurate_sums = {
                'overtime_actual': 0.0,
                'attendance_planned': 0.0,
            }

            for day in record.day_ids:
                for key in sums:
                    sums[key] += getattr(day, key)

                if day.date <= fields.date.today():
                    for key in accurate_sums:
                        accurate_sums[key] += getattr(day, key)

            record.update(sums)
            record.update(accurate_sums)


    @api.depends('vacation_spent', 'vacation_new')
    def _compute_vacation_carryover(self):
        for record in self:
            sums = {
                'vacation_spent': 0,
                'vacation_new': 0,
            }

            for ts in self.search(self.get_carryover_domain(record)):
                for key in sums:
                    sums[key] += getattr(ts, key)

            record.vacation_carryover = sums['vacation_new'] - sums['vacation_spent']


    @api.depends('vacation_carryover', 'vacation_spent', 'vacation_new')
    def _compute_vacation_total(self):
        for record in self:
            record.vacation_total = record.vacation_carryover - record.vacation_spent + record.vacation_new


    @api.depends('vacation_spent', 'vacation_new')
    def _compute_vacation_merged(self):
        for record in self:
            record.vacation_merged = record.vacation_new - record.vacation_spent


    @api.depends('overtime_actual', 'overtime_correction')
    def _compute_overtime_carryover(self):
        for record in self:
            sums = {
                'overtime_actual': 0.0,
                'overtime_correction': 0.0,
            }

            for ts in self.search(self.get_carryover_domain(record)):
                for key in sums:
                    sums[key] += getattr(ts, key)

            record.overtime_carryover = sums['overtime_actual'] + sums['overtime_correction']


    def _compute_overtime_correction_ids(self):
        for record in self:
            domain = [
                ('employee_id', '=', record.employee_id.id),
                ('date', '>=', record.date_from),
                ('date', '<=', record.date_to),
            ]
            record.overtime_correction_ids = self.env['dp.overtime'].search(domain)


    @api.depends('overtime_carryover', 'overtime_actual', 'overtime_correction')
    def _compute_overtime_total(self):
        for record in self:
            record.overtime_total = record.overtime_carryover + record.overtime_actual + record.overtime_correction


    @api.depends('overtime_actual', 'overtime_correction')
    def _compute_overtime_merged(self):
        for record in self:
            record.overtime_merged = record.overtime_actual + record.overtime_correction


    def _compute_date_effective_carryover(self):
        for record in self:
            ts = self.search(self.get_carryover_domain(record), limit=1)
            record.date_effective_carryover = ts.date_to if ts else record.date_from


    def _compute_timesheet_in_hours(self):
        for record in self:
            sums = {
                'vacation_spent_in_hours': 0.0,
                'sickness_spent_in_hours': 0.0,
                'others_spent_in_hours': 0.0,
            }

            for day in record.day_ids:
                for key in sums:
                    sums[key] += getattr(day, key)

            record.update(sums)


    @api.constrains('date_from', 'date_to')
    def _check_same_month(self):
        for record in self:
            if not ((record.date_from.month == record.date_to.month) and
                    (record.date_from.year == record.date_to.year)):
                raise ValidationError(_('Der Zeitraum des Time Report muss '
                    'vollständig innerhalb eines Monats liegen.'))


    @api.constrains('attendance_planned', 'attendance_actual',
        'compensation_spent', 'travel_time', 'overtime_actual',
        'vacation_spent', 'sickness_spent', 'others_spent', 'vacation_new',
        'overtime_correction')
    def _check_edit_only_when_open(self):
        for record in self:
            if record.state != 'open':
                msg = _('Der Time Report "%s" ist nicht mehr offen und kann '
                    'deshalb nicht mehr geändert werden.')
                msg %= record.display_name
                raise ValidationError(msg)


    @api.model
    def create(self, vals):
        res = super().create(vals)
        res._prepare()
        return res


    def write(self, vals):
        recreate_days = set()

        for record in self:
            if ('date_from' in vals) and (fields.Date.to_date(vals['date_from']) != record.date_from):
                recreate_days.add(record)

            if ('date_to' in vals) and (fields.Date.to_date(vals['date_to']) != record.date_to):
                recreate_days.add(record)

        res = super().write(vals)

        for ts in recreate_days:
            ts._prepare()

        return res


    @api.multi
    def check_attendances(self):
        self.ensure_one()

        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('check_in', '>=', self.date_from),
            ('check_in', '<=', self.date_to),
        ])
        for attendance in attendances:
            if not attendance.check_in or not attendance.check_out:
                msg = _('Es muss bei allen Anwesenheitszeiten Einchecken '
                    'und Auschecken gesetzt sein.\n'
                    '(siehe %s - %s)')
                msg %= (attendance.check_in, attendance.check_out)
                raise ValidationError(msg)


    def action_recalculate(self):
        for record in self.with_context(until_today=False):
            record.day_ids.calculate()

            # This should have been triggered automatically already, but it
            # may be useful sometimes. Actually it should be called once for
            # any day which is calculated above. That is inefficient.
            record._compute_timesheet()

            record.calculate()


    @api.multi
    def action_confirm(self):
        self.ensure_one()
        assert self.state == 'open'
        self.check_attendances()

        if self.manager_id:
            self.message_subscribe(self.manager_id.partner_id.ids)

        self.state = 'awaiting_approval'


    def action_approve(self):
        self.ensure_one()
        assert self.state == 'awaiting_approval'

        if self.user_id:
            self.message_subscribe(self.user_id.partner_id.ids)

        self.state = 'approved'


    def action_reject(self):
        self.ensure_one()
        assert self.state == 'awaiting_approval'

        self.state = 'open'


    def action_open(self):
        self.ensure_one()
        assert self.state == 'approved'

        self.state = 'open'


    def action_attendances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Anwesenheitszeiten',
            'res_model': 'hr.attendance',
            'view_type': 'form',
            'view_mode': 'tree,kanban,form',
            'domain': [
                ('employee_id', '=', self.employee_id.id),
                ('check_in', '>=', self.date_from),
                ('check_in', '<=', self.date_to),
            ],
        }


    def action_vacations(self):
        self.ensure_one()

        company = self.get_company()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Urlaube',
            'res_model': 'hr.leave',
            'view_type': 'form',
            'views': [
                (self.env.ref('hr_holidays.hr_leave_view_tree').id, 'tree'),
                (self.env.ref('hr_holidays.hr_leave_view_form').id, 'form'),
            ],
            'domain': [
                ('employee_id', '=', self.employee_id.id),
                ('date_from', '>=', self.date_from),
                ('date_to', '<=', self.date_to),
                ('holiday_status_id', '=', company.leave_type_vacation.id),
            ],
            'context': {
                'default_holiday_status_id': company.leave_type_vacation.id,
            },
        }


    def action_leave_allocations(self):
        self.ensure_one()

        company = self.get_company()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Urlaubszuschreibungen',
            'res_model': 'hr.leave.allocation',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': {
                'default_holiday_status_id': company.leave_type_vacation.id,
            },
            'domain': [
                ('employee_id', '=', self.employee_id.id),
                ('date_effective', '>=', self.date_from),
                ('date_effective', '<=', self.date_to),
                ('holiday_status_id', '=', company.leave_type_vacation.id),
            ],
        }


    def calculate(self):
        for record in self:
            vals = {
                'vacation_new': 0,
                'overtime_correction': 0.0,
            }

            company = self.get_company()

            # vacation_new
            domain = [
                ('employee_id', '=', record.employee_id.id),
                ('date_effective', '>=', record.date_from),
                ('date_effective', '<=', record.date_to),
                ('state', '=', 'validate'),
                ('holiday_status_id', '=', company.leave_type_vacation.id),
            ]
            for allocation in self.env['hr.leave.allocation'].search(domain):
                vals['vacation_new'] += allocation.number_of_days

            # overtime_correction
            domain = [
                ('employee_id', '=', record.employee_id.id),
                ('date', '>=', record.date_from),
                ('date', '<=', record.date_to),
            ]
            for overtime in self.env['dp.overtime'].search(domain):
                vals['overtime_correction'] += overtime.hours

            record.write(vals)


    @api.model
    def recalculate_affected(self, employee, date):
        domain = [
            ('employee_id', '=', employee.id),
            ('date_from', '<=', date),
            ('date_to', '>=', date),
        ]
        sheet = self.search(domain)
        sheet.calculate()


    @api.model
    def cron_create_timesheets(self):
        DpTimesheet = self.env['dp.timesheet']

        date_from = dp_tools.first_day_of_current_month()
        date_to = dp_tools.last_day_of_current_month()

        for employee in self.env['hr.employee'].search([]):
            domain = [
                ('employee_id', '=', employee.id),
                ('date_from', '=', date_from),
            ]
            if not DpTimesheet.search_count(domain):
                vals = {
                    'employee_id': employee.id,
                    'date_from': date_from,
                    'date_to': date_to,
                }
                DpTimesheet.create(vals)


    @api.model
    def get_company(self):
        c = self.env.user.company_id

        if not (c.leave_type_vacation and c.leave_type_sickness and c.leave_type_public_holiday):
            # XXX At least when called via RPC the exception isn't visible anywhere
            raise UserError(_('Bitte konfigurieren Sie zuerst die '
                'Abwesenheitstypen in den Unternehmensdaten.'))

        return c


    @api.model
    def _message_get_auto_subscribe_fields(self, updated_fields, auto_follow_fields=None):
        res = super()._message_get_auto_subscribe_fields(updated_fields, auto_follow_fields)
        res.append('manager_id')
        return res


    def _track_subtype(self, init_values):
        if 'state' in init_values and self.state == 'awaiting_approval':
            return 'dp_hr.mt_timesheet_confirmed'
        if init_values.get('state') == 'awaiting_approval' and self.state == 'approved':
            return 'dp_hr.mt_timesheet_approved'
        if init_values.get('state') == 'awaiting_approval' and self.state == 'open':
            return 'dp_hr.mt_timesheet_rejected'
        if init_values.get('state') == 'approved' and self.state == 'open':
            return 'dp_hr.mt_timesheet_reopened'

        return super()._track_subtype(init_values)


    def _prepare(self):
        for record in self:
            record.day_ids.unlink()

            # The constraint ensures that date_from and date_to are in the same month
            for day in range(record.date_from.day, record.date_to.day + 1):
                vals = {
                    'timesheet_id': record.id,
                    'date': '%04d-%02d-%02d' % (record.date_from.year, record.date_from.month, day),
                }
                self.env['dp.timesheet.day'].create(vals)

            record.action_recalculate()


    @api.model
    def postinstall_demo(self):
        user = self.env.ref('base.user_demo')
        user.groups_id = [(4, self.env.ref('base.group_user').id, 0)]


class DpTimesheetDay(models.Model):
    _name = 'dp.timesheet.day'
    _description = 'Time Report - Tag'
    _order = 'date'


    timesheet_id = fields.Many2one('dp.timesheet', 'Time Report', required=True, ondelete='cascade')
    date = fields.Date('Datum', required=True)
    contract_id = fields.Many2one('hr.contract', 'Vertrag', help='An diesem Tag gültiger Vertrag')
    attendance_planned = fields.Float('Geplant', digits=dp.get_precision('HR Time'))
    attendance_actual = fields.Float('Anwesenheit', digits=dp.get_precision('HR Time'))
    compensation_spent = fields.Integer('Zeitausgleich')
    travel_time = fields.Float('Reisezeit', digits=dp.get_precision('HR Time'))
    overtime_actual = fields.Float('Mehrstunden', digits=dp.get_precision('HR Time'))
    vacation_spent = fields.Integer('Urlaub', help='In Tagen')
    sickness_spent = fields.Integer('Krankenstand', help='In Tagen')
    others_spent = fields.Integer('Sonstiges')
    vacation_spent_in_hours = fields.Float('Konsumierter Urlaub in Stunden', help='In Stunden',
        compute='_compute_in_hours', digits=dp.get_precision('HR Time'))
    sickness_spent_in_hours = fields.Float('Krankenstandstage in Stunden', compute='_compute_in_hours',
        digits=dp.get_precision('HR Time'))
    others_spent_in_hours = fields.Float('Sonstiges in Stunden', compute='_compute_in_hours',
      digits=dp.get_precision('HR Time'))
    weekday = fields.Char('WT', compute='_compute_weekday', help='Wochentag')


    @api.multi
    def _compute_in_hours(self):
        for record in self:
            attendance_planned = 0.0

            for attendance in record.get_planned_attendances():
                attendance_planned += attendance.hour_to - attendance.hour_from

            record.vacation_spent_in_hours = record.vacation_spent * attendance_planned
            record.sickness_spent_in_hours = record.sickness_spent * attendance_planned
            record.others_spent_in_hours = record.others_spent * attendance_planned


    @api.multi
    def _compute_weekday(self):
        for record in self:
            record.weekday = dp_tools.day_of_the_week_short(record.date)


    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False):
        if self.env.context.get('until_today'):
            # The context value is set on the time reports action.
            # Note that changes made here are effective for everything
            # that is reached through there, that includes calculation
            # buttons. When that isn't desired care must be taken to remove
            # the value before accessing the data.
            # A better place could be to put the value just on the day_ids
            # field in the form view, but it doesn't seem to work.

            # In the current timesheet show only the entries until today
            args.append(('date', '<=', fields.Date.today()))

            order = 'date DESC'

        return super().search(args, offset, limit, order, count)


    @api.model
    def create(self, vals):
        res = super().create(vals)
        res.calculate()
        return res


    @api.multi
    def get_planned_attendances(self):
        self.ensure_one()

        dayofweek = str(self.date.weekday())
        # sudo: Allow users to calculate timesheets
        contract = self.sudo().contract_id
        planned_attendances = contract.resource_calendar_id.attendance_ids
        planned_attendances = planned_attendances.filtered(lambda r: r.dayofweek == dayofweek)

        return planned_attendances


    def clean_context(self):
        """
        Remove context keys that constrain leave searches
        """

        context = self.env.context.copy()

        if 'only_vacations' in context:
            del context['only_vacations']
        if 'only_sicknesses' in context:
            del context['only_sicknesses']
        if 'only_public_holidays' in context:
            del context['only_public_holidays']

        return context


    def calculate(self):
        for record in self:
            vals = {
                'attendance_planned': 0.0,
                'attendance_actual': 0.0,
                'travel_time': 0.0,
            }

            employee = record.timesheet_id.employee_id

            # contract_id
            domain = [
                ('employee_id', '=', employee.id),
                ('date_start', '<=', record.date),
                '|',
                ('date_end', '>=', record.date),
                ('date_end', '=', False),
            ]
            # sudo: Allow users to create attendances, vacations, etc.
            Contract = self.env['hr.contract'].sudo()
            # Archived contracts must be considered as well, otherwise
            # the planned attendance would disappear, creating lots of
            # false overtime.
            Contract = Contract.with_context(active_test=False)
            contract = Contract.search(domain)

            # In order to allow multiple contracts per month while keeping
            # calculation of the planned attendance simple we store the
            # applicable contract for each day. That must be an unambiguous
            # assignment.
            if len(contract) > 1:
                msg = _('Mitarbeiter dürfen pro Tag nur einen Vertrag haben. '
                    'Aktuell hat "%s" am %s %d Verträge.')
                msg %= (employee.name, record.date, len(contract))
                raise UserError(msg)

            vals['contract_id'] = contract.id

            planned_attendances = record.get_planned_attendances()

            # There should not be an attendance in the future
            today = fields.Date.today()
            if record.date <= today:
                # attendance_actual, travel_time
                domain = [
                    ('employee_id', '=', employee.id),
                    # When comparing Datetime with Date in search() Odoo
                    # will coerce the Date into Datetime with the time
                    # component depending on the operator. For <= it's
                    # 23:59:59.999999.
                    ('check_in', '<=', record.date),
                ]
                if record.date == today:
                    domain.extend([
                        '|',
                        ('check_out', '=', False),
                        ('check_out', '>=', record.date),
                    ])
                else:
                    domain.extend([
                        ('check_out', '>=', record.date),
                    ])
                for attendance in self.env['hr.attendance'].search(domain):
                    # checks if the check_in date equals the date that will be calced
                    if attendance.check_in and attendance.check_in.date() == record.date:
                        check_out = attendance.check_out if attendance.check_out else fields.Datetime.now()
                        delta = check_out - attendance.check_in
                        delta = delta.total_seconds() / 60 / 60
                        if attendance.is_travel_time:
                            vals['travel_time'] += delta
                        else:
                            vals['attendance_actual'] += delta

            # others_spent
            company = self.env['dp.timesheet'].get_company()

            # Remove certain context values to fetch all hr.leave values
            leave_context = self.clean_context()

            HRLeave = self.with_context(leave_context).env['hr.leave']

            domain = [
                ('employee_id', '=', employee.id),
                ('date_from', '<=', record.date),
                ('date_to', '>=', record.date),
                ('state', '=', 'validate'),
                ('holiday_status_id', '!=', company.leave_type_vacation.id),
                ('holiday_status_id', '!=', company.leave_type_compensation.id),
                ('holiday_status_id', '!=', company.leave_type_sickness.id),
            ]
            vals['others_spent'] = 1 if HRLeave.search_count(domain) and planned_attendances else 0

            # sickness_spent
            del domain[-3:]
            domain.append(('holiday_status_id', '=', company.leave_type_sickness.id))
            if (not vals['others_spent']) and planned_attendances and HRLeave.search_count(domain):
                vals['sickness_spent'] = 1
            else:
                vals['sickness_spent'] = 0

            # vacation_spent
            domain.pop()
            domain.append(('holiday_status_id', '=', company.leave_type_vacation.id))
            if not (vals['others_spent'] or vals['sickness_spent']) and \
                    planned_attendances and HRLeave.search_count(domain):
                vals['vacation_spent'] = 1
            else:
                vals['vacation_spent'] = 0

            # compensation_spent
            domain.pop()
            domain.append(('holiday_status_id', '=', company.leave_type_compensation.id))
            if not (vals['others_spent'] or vals['sickness_spent']) and \
                planned_attendances and HRLeave.search_count(domain):
                vals['compensation_spent'] = 1
            else:
                vals['compensation_spent'] = 0

            # attendance_planned
            if vals['others_spent'] or vals['sickness_spent'] or \
                    vals['vacation_spent'] or (not contract):
                vals['attendance_planned'] = 0.0
            else:
                for attendance in planned_attendances:
                    vals['attendance_planned'] += attendance.hour_to - attendance.hour_from

            # overtime_actual
            vals['overtime_actual'] = vals['attendance_actual'] - vals['attendance_planned'] + vals['travel_time']

            # Only write values that changed, don't rewrite all values. That
            # allows to calculate approved timesheets.
            vals = record.get_changed_values(vals)
            if vals:
                record.write(vals)


    @api.multi
    def get_changed_values(self, vals):
        """
        Checks if the any values have changed and returns only changed ones
        :param vals: vals to be evaluated
        :return: dict of final vals to be written, meaning the ones which have changed
        """

        self.ensure_one()

        result = {}
        precision = self.env['decimal.precision'].precision_get('HR Time')

        for val_key in vals:
            old_value = self.__getattribute__(val_key)
            new_value = vals[val_key]

            if isinstance(old_value, float):
                if float_compare(old_value, new_value, precision_digits=precision):
                    result[val_key] = new_value
            elif isinstance(old_value, models.Model):
                compare = new_value if isinstance(new_value, (list, tuple)) else [new_value]
                if set(old_value.ids) != set(compare):
                    result[val_key] = new_value
            else:
                if old_value != vals[val_key]:
                    result[val_key] = new_value

        return result


    @api.model
    def recalculate_affected(self, employee, date_from, date_to):
        if not date_to:
            date_to = fields.Date.today()

        domain = [
            ('timesheet_id.employee_id', '=', employee.id),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]
        days = self.search(domain)
        days.calculate()


class DpLeaveTemplate(models.Model):
    _name = 'dp.leave.template'
    _description = 'Feiertagsvorlage'
    _order = 'id desc'
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Die Beschreibung muß eindeutig sein.'),
    ]


    name = fields.Char('Beschreibung', required=True)
    apply_to_new_employees = fields.Boolean('Für neue Mitarbeiter übernehmen')
    line_ids = fields.One2many('dp.leave.template.line', 'template_id', 'Zeilen')


class DpLeaveTemplateLine(models.Model):
    _name = 'dp.leave.template.line'
    _description = 'Feiertagsvorlagenzeile'
    _order = 'date'
    _sql_constraints = [
        ('name_unique', 'UNIQUE(template_id, date)', 'Ein Tag darf pro Vorlage nur einmal vorkommen.'),
    ]


    template_id = fields.Many2one('dp.leave.template', 'Feiertagsvorlage', required=True, ondelete='cascade')
    name = fields.Char('Beschreibung', required=True)
    date = fields.Date('Datum', required=True)


class DpOvertime(models.Model):
    _name = 'dp.overtime'
    _description = 'Mehrstundenkorrektur'
    _order = 'date desc'


    name = fields.Char('Beschreibung', required=True)
    date = fields.Date('Datum', required=True, help='Datum an dem die Änderung durchgeführt wird.')
    employee_id = fields.Many2one('hr.employee', 'Mitarbeiter', required=True)
    hours = fields.Float('Anzahl Stunden', required=True, digits=dp.get_precision('HR Time'), help='Der Wert kann sowohl positiv als auch negativ sein.')


    @api.model
    def create(self, vals):
        res = super().create(vals)

        self.env['dp.timesheet'].recalculate_affected(res.employee_id, res.date)

        return res


    def write(self, vals):
        DpTimesheet = self.env['dp.timesheet']

        affected_periods = []

        for record in self:
            affected_periods.append((record.employee_id, record.date))

        res = super().write(vals)

        for ap in affected_periods:
            DpTimesheet.recalculate_affected(*ap)

        for record in self:
            DpTimesheet.recalculate_affected(record.employee_id, record.date)

        return res


    def unlink(self):
        affected_periods = []

        for record in self:
            affected_periods.append((record.employee_id, record.date))

        res = super().unlink()

        for ap in affected_periods:
            self.env['dp.timesheet'].recalculate_affected(*ap)

        return res
