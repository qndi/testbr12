# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).
from odoo.tests.common import TransactionCase


class TestDpBmd(TransactionCase):
    """ BMD Export Tests """

    def setUp(self):
        super(TestDpBmd, self).setUp()
        self.BmdExport = self.env['bmd.export']
        self.BmdExportWizard = self.env['bmd.export.wizard']
        self.AccountInvoice = self.env['account.invoice']
        self.AccountAccount = self.env['account.account']
        self.demo_user = self.env.ref('base.user_demo')
        self.demo_customer = self.env.ref('base.res_partner_12')  # Azure Interior
        self.demo_product_5 = self.env.ref('product.product_product_5')
        self.demo_product_6 = self.env.ref('product.product_product_6')
        self.demo_product_4d = self.env.ref('product.product_product_4d')
        self.demo_tax_10 = self.env.ref('l10n_at.1_tax_at_mwst_10')
        self.demo_tax_20 = self.env.ref('l10n_at.1_tax_at_mwst_20')
        self.demo_account_10 = self.env.ref('l10n_at.1_chart4010')
        self.demo_account_20 = self.env.ref('l10n_at.1_chart4000')

    def _get_invoice_line_data(self):
        invoice_line_data = [
            (0, 0,
                {
                    'product_id': self.demo_product_5.id,
                    'quantity': 5.0,
                    'name': self.demo_product_5.name,
                    'price_unit': 123.67,
                    'account_id': self.demo_account_20.id,
                    'invoice_line_tax_ids': [(6, 0, [self.demo_tax_20.id])],
                }),
            (0, 0,
                {
                    'product_id': self.demo_product_6.id,
                    'quantity': 7.0,
                    'name': self.demo_product_6.name,
                    'price_unit': 200.4,
                    'account_id': self.demo_account_20.id,
                    'invoice_line_tax_ids': [(6, 0, [self.demo_tax_20.id])],
                }),
            (0, 0,
                {
                    'product_id': self.demo_product_4d.id,
                    'quantity': 7.0,
                    'name': self.demo_product_4d.name,
                    'price_unit': 0.99,
                    'account_id': self.demo_account_20.id,
                    'invoice_line_tax_ids': [(6, 0, [self.demo_tax_20.id])],
                }),
        ]
        return invoice_line_data

    def _create_invoice(self, invoice_line_data, invoice_type='out_invoice'):
        invoice = self.AccountInvoice.sudo(self.demo_user.id).create(dict(
            partner_id=self.demo_customer.id,
            type=invoice_type,
            invoice_line_ids=invoice_line_data
        ))
        return invoice

    def _check_invoice(self, expected_data, invoice, wizard):
        export_invoice_data = wizard.get_invoice_data()[0]
        count = 0
        for row in export_invoice_data:
            if row['belegnr'] == invoice.number:
                row_data = {'betrag': row.get('betrag'),
                            'prozent': row.get('prozent'),
                            'steuer': row.get('steuer')}
                self.assertEquals(row_data, expected_data[count])
                count += 1

    def test_bmd_export_flags(self):
        """ Create an invoice and test if bmd_export flags are set on invoice and partner objects """
        invoice = self._create_invoice(self._get_invoice_line_data())
        invoice.action_invoice_open()
        # newly created and opened invoices should always be exported
        self.assertEquals(invoice.bmd_export, True)
        # if customer was already exported previously (bmd_export_date = True), bmd_export should be False else True
        self.assertEquals(invoice.partner_id.commercial_partner_id.bmd_export,
                          False if invoice.partner_id.commercial_partner_id.bmd_export_date else True)

    def test_bmd_export_counts(self):
        """ Create new invoice, then create bmd_export through the wizard, and check if "counts" are correct """
        invoice = self._create_invoice(self._get_invoice_line_data())
        invoice.action_invoice_open()
        wizard = self.BmdExportWizard.create({})
        res = wizard.do_export()
        export = self.BmdExport.browse(res.get('res_id'))
        self.assertGreaterEqual(export.invoice_count, 1)
        if not invoice.partner_id.commercial_partner_id.bmd_export_date:
            self.assertGreaterEqual(export.customer_count, 1)

    def test_bmd_export_partner_write(self):
        """ Write street on partner and check if bmd_export flag is set and export will have 1 customer """
        self.demo_customer.write({'street': 'Demo Street'})
        self.assertEquals(self.demo_customer.bmd_export, True)
        wizard = self.BmdExportWizard.create({})
        res = wizard.do_export()
        export = self.BmdExport.browse(res.get('res_id'))
        self.assertEquals(export.customer_count, 1)

    def test_bmd_export_out_invoice_20_grouped(self):
        """ Create new invoice with predefined invoice lines, create new BMD Export and then compare exported values """
        expected_data = [{
                        'betrag': '2425,38',
                        'prozent': '20,0',
                        'steuer': '-404,23'
                    },
                    {
                        'betrag': '8,32',
                        'prozent': '20,0',
                        'steuer': '-1,39'
                    }]

        invoice_line_data = self._get_invoice_line_data()

        invoice_line_data[2][2]['account_id'] = self.demo_account_10.id
        invoice = self._create_invoice(invoice_line_data)
        invoice.action_invoice_open()
        wizard = self.BmdExportWizard.create({})
        self._check_invoice(expected_data, invoice, wizard)

    def test_bmd_export_out_invoice_10_20_grouped(self):
        """ Create new invoice with predefined invoice lines, create new BMD Export and then compare exported values """
        expected_data = [{
                        'betrag': '2425,38',
                        'prozent': '20,0',
                        'steuer': '-404,23'
                    },
                    {
                        'betrag': '7,62',
                        'prozent': '10,0',
                        'steuer': '-0,69'
                    }]

        invoice_line_data = self._get_invoice_line_data()

        invoice_line_data[2][2]['invoice_line_tax_ids'] = [(6, 0, [self.demo_tax_10.id])]
        invoice = self._create_invoice(invoice_line_data)
        invoice.action_invoice_open()
        wizard = self.BmdExportWizard.create({})
        self._check_invoice(expected_data, invoice, wizard)

    def test_bmd_export_out_refund_20_grouped(self):
        """ Create new invoice with predefined invoice lines, create new BMD Export and then compare exported values """
        expected_data = [{
                        'betrag': '-2425,38',
                        'prozent': '20,0',
                        'steuer': '404,23'
                    },
                    {
                        'betrag': '-8,32',
                        'prozent': '20,0',
                        'steuer': '1,39'
                    }]

        invoice_line_data = self._get_invoice_line_data()

        invoice_line_data[2][2]['account_id'] = self.demo_account_10.id
        invoice = self._create_invoice(invoice_line_data, invoice_type='out_refund')
        invoice.action_invoice_open()
        wizard = self.BmdExportWizard.create({})
        self._check_invoice(expected_data, invoice, wizard)

    def test_bmd_export_out_refund_10_20_grouped(self):
        """ Create new invoice with predefined invoice lines, create new BMD Export and then compare exported values """
        expected_data = [{
                        'betrag': '-2425,38',
                        'prozent': '20,0',
                        'steuer': '404,23'
                    },
                    {
                        'betrag': '-7,62',
                        'prozent': '10,0',
                        'steuer': '0,69'
                    }]

        invoice_line_data = self._get_invoice_line_data()

        invoice_line_data[2][2]['invoice_line_tax_ids'] = [(6, 0, [self.demo_tax_10.id])]
        invoice = self._create_invoice(invoice_line_data, invoice_type='out_refund')
        invoice.action_invoice_open()
        wizard = self.BmdExportWizard.create({})
        self._check_invoice(expected_data, invoice, wizard)

    def test_bmd_export_partner_write_children(self):
        """Write payment property to partner with children - children be written with payment term as well"""
        self.assertTrue(
            self.demo_customer.write({'vat': 'AT123456789'})
        )
        self.assertEquals(self.demo_customer.bmd_export, True)
        if self.demo_customer.child_ids:
            self.assertEquals(self.demo_customer.child_ids[0].vat, self.demo_customer.vat)
            self.assertEquals(self.demo_customer.child_ids[0].bmd_export, True)

        wizard = self.BmdExportWizard.create({})
        res = wizard.do_export()
        export = self.BmdExport.browse(res.get('res_id'))
        changed_partners = len(self.demo_customer.child_ids) + 1
        self.assertEquals(export.customer_count, changed_partners)
