# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.tools import formatLang, round as o_round


class DpTimesheet(models.Model):
    _inherit = 'dp.timesheet'


    project_hours = fields.Float('Projektzeiten', compute='_compute_timesheet', store=True,
        digits=dp.get_precision('HR Time'))
    chargeable_hours = fields.Float('Chargeable', compute='_compute_timesheet', store=True,
        digits=dp.get_precision('HR Time'))
    chargeability = fields.Integer('Chargeability', compute='_compute_chargeability', store=True,
        digits=dp.get_precision('HR Time'), help='Berechnung: Chargeable / Geplante Anwesenheit')
    billable_hours = fields.Float('Billable', compute='_compute_billability', store=True,
        digits=dp.get_precision('HR Time'))
    billability = fields.Integer('Billability', compute='_compute_billability', store=True,
        digits=dp.get_precision('HR Time'), help='Berechnung: Billable / Geplante Anwesenheit')
    department_id = fields.Many2one('hr.department', 'Department', related='employee_id.department_id', store=True)


    @api.depends('day_ids', 'day_ids.attendance_planned', 'day_ids.attendance_actual',
        'day_ids.overtime_actual', 'day_ids.vacation_spent', 'day_ids.sickness_spent',
        'day_ids.others_spent', 'day_ids.project_hours', 'day_ids.chargeable_hours')
    def _compute_timesheet(self):
        res = super()._compute_timesheet()

        for record in self:
            sums = {
                'project_hours': 0.0,
                'chargeable_hours': 0.0,
            }

            for day in record.day_ids:
                for key in sums:
                    sums[key] += getattr(day, key)

            record.update(sums)

        return res


    @api.depends('chargeable_hours', 'attendance_planned')
    def _compute_chargeability(self):
        for record in self:
            if record.attendance_planned:
                record.chargeability = o_round(record.chargeable_hours * 100 / record.attendance_planned)
            else:
                record.chargeability = 0.0


    @api.depends('day_ids.billable_hours', 'day_ids.attendance_planned')
    def _compute_billability(self):
        for record in self:
            sums = {
                'attendance_planned': 0.0,
                'billable_hours': 0.0,
            }
            # get the planned attendance to the current date and sumation of billable_hours
            for day in record.day_ids.filtered(lambda x: fields.Date.from_string(x.date) <= fields.date.today()):
                for key in sums:
                    sums[key] += getattr(day, key)

            record.update(sums)

            if sums['attendance_planned']:
                record.billability = o_round(sums['billable_hours'] * 100 / sums['attendance_planned'])
            else:
                record.billability = 0.0


    def action_project_hours(self):
        self.ensure_one()

        action = self.env.ref('hr_timesheet.act_hr_timesheet_line').read()[0]
        action['domain'] = [
            ('user_id', '=', self.user_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        action['view_mode'] = 'tree,form'
        action['views'] = [x for x in action['views'] if x[1] in ['tree', 'form']]
        action['name'] = _('Projektzeiten von %s') % self.employee_id.name

        return action


    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        result = super().read_group(domain, fields, groupby,
            offset=offset, limit=limit, orderby=orderby, lazy=lazy)

        for entry in result:
            if entry.get('attendance_planned', False):
                entry['chargeability'] = entry['chargeable_hours'] * 100 / entry['attendance_planned']
                entry['billability'] = entry['billable_hours'] * 100 / entry['attendance_planned']

        return result


    def action_approve(self):
        res = super().action_approve()

        for record in self:
            record._set_validation_date()

        return res


    def action_reject(self):
        res = super().action_reject()

        for record in self:
            record._set_validation_date()

        return res


    def action_open(self):
        res = super().action_open()

        for record in self:
            record._set_validation_date()

        return res


    def _set_validation_date(self):
        self.ensure_one()

        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'approved'),
        ]
        sheet = self.search(domain, limit=1, order='date_from DESC')

        # hr.employee,timesheet_validated is an enterprise field, it doesn't
        # exist in the community edition. It seems nothing happens when
        # assigning to it, not even an unknown fields warning. We still avoid
        # that, however. Official recommendations on this point are unknown
        # at the moment.
        try:
            self.employee_id.timesheet_validated
        except AttributeError:
            pass
        else:
            # In case no other timesheet exists during approval there's at least
            # the one we just confirmed, thus the right date is set. During the
            # other operations the right date or False is set.
            self.employee_id.timesheet_validated = sheet.date_to


    def get_project_data(self):
        """
        Prepare the data for the projects summary table on the report.
        We can't simply take the project and chargeable hours from the
        day_ids since that's the total sum per day but we want to see
        how that splits up on the individual projects.
        """

        self.ensure_one()

        chargeable = {}
        non_chargeable = {}

        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        for line in self.env['account.analytic.line'].search(domain):
            project = line.project_id
            data = chargeable if project.is_chargeable else non_chargeable
            if project.id not in data:
                data[project.id] = {
                    'name': project.name,
                    'project_hours': 0.0,
                }

            data[project.id]['project_hours'] += line.unit_amount

        def transform(data):
            res = list(data.values())

            for i in res:
                # formatLang() has disappeared from the QWeb context, so it
                # can't be used directly in the template anymore. It seems
                # t-field would do the right thing automatically, but can only
                # be used with actual fields and not plain values.
                # The recommended way isn't known yet. It could be that they
                # wanted to move the formatting to Python. It seems we should
                # deliver a fully formatted string to the template.
                i['project_hours'] = formatLang(self.env, i['project_hours'])

            return res

        return {
            'chargeable': transform(chargeable),
            'non_chargeable': transform(non_chargeable),
        }
