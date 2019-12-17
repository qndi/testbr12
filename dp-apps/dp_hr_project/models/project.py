# Copyright 2017-Today datenpol gmbh (<https://www.datenpol.at/>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import models, fields


class ProjectProject(models.Model):
    _inherit = 'project.project'


    is_chargeable = fields.Boolean('Chargeable', default=True,
        help='Zuordnung des Projekts in die Gruppe Chargeable bzw. '
            'Non-Chargeable im Time Report. Dieses Feld hat keine '
            'Auswirkungen auf die Zeiterfassung in den Aufgaben des Projekts. '
            'Die Zeiten können sowohl Billable, als auch Non-Billable sein, '
            'abhängig vom Vorhandensein eines Auftragselements.')
