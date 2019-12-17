# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/12.0/legal/licenses/licenses.html#licenses).

from odoo import api, fields, models, _
from odoo.addons.queue_job.jobrunner.__init__ import _start_runner_thread

runner_thread = None

import signal

class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_cr
    def _register_hook(self):
        super(ResCompany, self)._register_hook()
        # The problem here is, that this method is called every time when a new worker is spawn.
        # If workers=3, ist is called three times. Additionally it is called whenever a worker is recycled.

        # Another Issue:
        # When this worker is recycled while it is serving a job, then this job remains in state 'started'
        # TODO: Cronjob which detects an requeues such zombie jobs
        print("REGISTER_HOOK")
        import odoo
        r_thead = odoo.addons.queue_job.jobrunner.__init__.runner_thread
        if not r_thead:
            print("START THREAD")
            _start_runner_thread("dp_start_job_runner")
        pass

        # import os
        # import sys
        # from odoo.addons.queue_job.jobrunner.__init__ import QueueJobRunnerThread
        #
        # pid = os.fork()
        # if pid != 0:
        #     # parent
        #     pass
        # else:
        #     # child
        #     print(os.getppid())
        #     runner = QueueJobRunnerThread()
        #     runner.run()
        #     sys.exit(0)
