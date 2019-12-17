# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    max_work_without_break = fields.Float('Max. Arbeitszeit ohne Pause in Std.', default=6,
        help='Fügen Sie den Grenzwert für Warnungen bei Überschreitung der '
            'maximalen Stundenanzahl ohne Pause ein.')
    min_break_in_hours = fields.Float('Minimale Pause in Std.', default=0.5,
        help='Fügen Sie den Wert einer minimalen durchgängigen Pause ein. Bei '
            'Unterschreitung des Wertes wird eine Warnung im Time Report angezeigt.')
    max_work_per_day = fields.Float('Maximale Arbeitszeit pro Tag in Std.', default=10,
        help='Fügen Sie die maximal erlaubte Arbeitszeit pro Tag in Stunden ein. '
            'Bei Überschreitung dieser wird eine Warnung im Time Report angezeigt.')
    warning_work_on_weekends = fields.Boolean('Warnung bei Arbeit an Wochenenden', default=True,
        help='Bei aktivierter Option wird bei Wochenendarbeit eine Warnung '
            'im Time Report angezeigt.')
    warning_work_on_absent = fields.Boolean('Warnung bei Arbeit an Tagen mit Abwesenheit', default=True,
        help='Bei aktivierter Option wird bei Arbeit an Tagen mit Abwesenheit '
            '(Feiertag, Krankenstand oder Urlaubstag) eine Warnung im Time Report angezeigt.')
    earliest_work_begin = fields.Float('Frühester Arbeitsbeginn', default=6,
        help='Für Buchungen vor der definierten Uhrzeit wird im Time Report eine Warnung angezeigt.')
    latest_work_end = fields.Float('Spätestes Arbeitsende', default=20,
        help='Für Buchungen nach der definierten Uhrzeit wird im Time Report eine Warnung angezeigt.')
