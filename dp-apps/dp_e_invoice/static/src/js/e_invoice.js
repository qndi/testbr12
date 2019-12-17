odoo.define('dp.e_invoice', function (require) {
    var ActionManager = require('web.ActionManager');

    ActionManager.include({
        ir_actions_act_close_wizard_and_send_notification: function (action, options) {
            if (!this.dialog) {
                options.on_close();
            }
            this.dialog_stop();
            title = "Title";
            message = "Message"

            // get title
            if (action && action['title'] !== undefined) {
                title = action['title'];
            }

            // get message
            if (action && action['message'] !== undefined) {
                message = action['message'];
            }

            this.webclient.notification_manager.do_notify(title, message);
        },

    });
});


