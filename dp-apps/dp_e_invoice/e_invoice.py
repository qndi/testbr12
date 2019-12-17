# -*- coding: utf-8 -*-
# Copyright 2018-Today datenpol gmbh (<http://www.datenpol.at>)
# License OPL-1 or later (https://www.odoo.com/documentation/user/11.0/legal/licenses/licenses.html#licenses).

import logging
import os

try:
    from suds.client import Client
    from suds import WebFault
    from suds.wsse import Security, UsernameToken
except ImportError:
     Client = None
     Security = None
     UsernameToken = None
from odoo.exceptions import Warning
from xml.etree.ElementTree import Element, SubElement, tostring
import base64
from odoo.tools import config
from odoo.release import version
from .ssl_context import create_ssl_context, HTTPSTransport

_logger = logging.getLogger(__name__)

# logging.getLogger('suds.client').setLevel(logging.DEBUG)
# logging.getLogger('suds.transport').setLevel(logging.DEBUG)
# logging.getLogger('suds.xsd.schema').setLevel(logging.DEBUG)
# logging.getLogger('suds.wsdl').setLevel(logging.DEBUG)

ENCODING = 'UTF-8'
UNIT_TYPE = 'IntegerType'


class EInvoiceService:

    def __init__(self, env):
        wsdl_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'api/erb-invoicedelivery-200.wsdl')

        self.username = env['ir.config_parameter'].get_param('e_invoice.username')
        self.password = env['ir.config_parameter'].get_param('e_invoice.password')
        self.response_email_cc = env['ir.config_parameter'].get_param('e_invoice.response_email')
        self.environment = env['ir.config_parameter'].get_param('e_invoice.environment')
        self.odoo_version_string = 'Odoo %s' % version
        self.invoice_recipient_biller_id = env['ir.config_parameter'].get_param('e_invoice.invoice_recipient_biller_id')
        self.e_invoice = None

        self.environment = config.get('environment', 'TEST')
        if self.environment == 'PROD':
            test_mode = False
        else:
            test_mode = True

        sslverify = False
        cafile = None
        capath = None

        kwargs = {}
        sslContext = create_ssl_context(sslverify, cafile, capath)
        kwargs['transport'] = HTTPSTransport(sslContext)

        self.client = Client('file:///%s' % wsdl_file.lstrip('/'), **kwargs)
        self.test_mode = test_mode
        self.client.set_options(wsse=self._get_security_header())

    def _get_security_header(self):
        security = Security()
        token = UsernameToken(self.username, self.password)
        security.tokens.append(token)
        return security

    def save_e_invoice(self, e_invoice):
        self.e_invoice = e_invoice

    def get_e_invoice(self):
        return self.e_invoice

    def deliver_invoice(self, invoice, attachments=False):
        e_settings = self._get_settings(invoice.env)
        e_invoice = self._get_e_invoice(invoice)
        self.save_e_invoice(e_invoice)
        e_attachments = []

        if attachments and len(attachments) > 0:
            e_attachments = self._get_attachments(attachments)

        # Parameters deliverInvoice => invoice, embedded attachments, external attachments (not supported), settings
        try:
            response = self.client.service.deliverInvoice(e_invoice, e_attachments, [], e_settings)
        except WebFault as e:
            raise Warning(e)

        if 'Error' in response:
            error_text = u"Webservice Rückmeldung:\n"
            for error_detail in response.Error.ErrorDetail:
                error_text += error_detail.Message + '\n'
            raise Warning(unicode(error_text))
        elif 'Success' in response:
            return response.Success
        else:
            raise Warning(u'Antwort von E-Bund konnte nicht vearbeitet werden, bitte wenden sie sich an den Hersteller.')

    def get_response_email_address(self, env):
        # In case neither the system parameter nor the user e-mail is set,
        # then the company e-mail address happens to used. In case that
        # doesn't exist either then the eb:Email element is omitted.
        responseEmail = ''

        if env and env.user.email:
            responseEmail = env.user.email

        if self.response_email_cc:
            responseEmail = self.response_email_cc  # default Mail from Settings

        return responseEmail


    def _get_settings(self, env=False):
        responseEmail = self.get_response_email_address(env)

        settings = self.client.factory.create('ns0:DeliverySettingsType')
        settings.EmailSettings.AlternateResponseEmail = []
        settings.EmailSettings.AdditionalResponseEmail = []
        settings.EmailSettings.ResponseEmailCC = responseEmail
        settings.EmailSettings.ResponseEmailBCC = []
        settings.EmailSettings.SubjectPrefix = 'E-Rechnung '
        settings._test = self.test_mode

        return settings

    def _get_e_invoice(self, invoice):
        xml_invoice = self._transform_invoice_to_xml(invoice)
        xml_invoice_string = tostring(xml_invoice, ENCODING)
        _u = lambda t: t.decode('UTF-8', 'replace') if isinstance(t, str) else t
        _logger.info(_u(xml_invoice_string))
        b64_encoded_xml_invoice_string = base64.b64encode(xml_invoice_string)

        e_invoice = self.client.factory.create('ns0:DeliveryInvoiceType')
        e_invoice.value = b64_encoded_xml_invoice_string
        e_invoice._encoding = ENCODING

        return e_invoice

    def _get_attachments(self, attachments):
        attachment_list = []
        for attachment in attachments:
            attachment_type = self.client.factory.create('ns0:DeliveryEmbeddedAttachmentType')
            attachment_type._name = attachment['filename']
            attachment_type.value = attachment['data']
            attachment_list.append(attachment_type)
        return attachment_list

    def _transform_invoice_to_xml(self, invoice):
        attributes = {
            'xmlns': "http://www.w3.org/2000/09/xmldsig#",
            'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
            'xmlns:eb': "http://www.ebinterface.at/schema/4p2/",
            'eb:Language': "ger",
            'eb:DocumentTitle': "Invoice",
            'eb:InvoiceCurrency': "EUR",
            'eb:DocumentType': "Invoice",
            'eb:GeneratingSystem': self.odoo_version_string,

            #'xsi:schemaLocation': "http://www.ebinterface.at/schema/4p2/ http://www.ebinterface.at/schema/4p2/Invoice.xsd",
        }

        eb_invoice_element = Element('eb:Invoice', attrib=attributes)

        self._appendInvoiceNumber(eb_invoice_element, invoice)
        self._appendInvoiceDate(eb_invoice_element, invoice)
        self._appendDelivery(eb_invoice_element, invoice)
        self._appendBiller(eb_invoice_element, invoice)
        self._appendInvoiceRecipient(eb_invoice_element, invoice)
        self._appendInvoiceLinesAndDownPayments(eb_invoice_element, invoice)
        self._appendReductionAndSurchargeDetails(eb_invoice_element, invoice)
        self._appendTaxes(eb_invoice_element, invoice)
        self._appendTotalGrossAmount(eb_invoice_element, invoice)
        self._appendPayableAmount(eb_invoice_element, invoice)
        self._appendPaymentMethod(eb_invoice_element, invoice)
        self._appendPaymentConditions(eb_invoice_element, invoice)

        return eb_invoice_element

    def _appendInvoiceNumber(self, root, invoice):
        child = SubElement(root, 'eb:InvoiceNumber')
        if invoice.number and invoice.state == 'open':
            child.text = invoice.number
        else:
            errorMsg = 'Die Rechnung muss sich im Status \"Offen\" befinden'
            raise Warning(errorMsg)

    def _appendInvoiceDate(self, root, invoice):
        child = SubElement(root, 'eb:InvoiceDate')
        child.text = str(invoice.date_invoice)

    def _appendDelivery(self, root, invoice):
        delivery = SubElement(root, 'eb:Delivery')
        period = SubElement(delivery, 'eb:Period')
        from_date = SubElement(period, 'eb:FromDate')
        to_date = SubElement(period, 'eb:ToDate')
        if not invoice.period_of_performance_from or not invoice.period_of_performance_to:
            errorMsg = u'Das Feld \"Leistungszeitraum für E-Rechnung\" muss hinterlegt sein'
            raise Warning(errorMsg)

        from_date.text = str(invoice.period_of_performance_from)
        to_date.text = str(invoice.period_of_performance_to)

        # Lieferadresse mitsenden wenn vorhanden
        if invoice.partner_shipping_id:
            self._appendAddress(delivery, invoice.partner_shipping_id)

    def _appendBiller(self, root, invoice):
        # Rechnungssteller
        biller = SubElement(root, 'eb:Biller')
        biller_partner = invoice.company_id.partner_id

        # if not biller_partner.email:
        #     raise Warning("Bei dem in den Unternehmensdaten zugeordneten Partner, ist keine EMailadresse hinterlegt!")

        vat_number = SubElement(biller, 'eb:VATIdentificationNumber')
        vat_number.text = biller_partner.vat

        # get company partner as billerPartner
        self._appendAddress(biller, biller_partner, self.get_response_email_address(invoice.env))

        invoice_recipients_biller_id = SubElement(biller, 'eb:InvoiceRecipientsBillerID')
        invoice_recipients_biller_id.text = self.invoice_recipient_biller_id

    def _appendInvoiceRecipient(self, root, invoice):
        recipient = SubElement(root, 'eb:InvoiceRecipient')

        # Die VAT ist nicht notwendig, da zB ein Finanzamt auch keine VAT hat

        vat_number = SubElement(recipient, 'eb:VATIdentificationNumber')
        if invoice.partner_id.vat:
            vat_number.text = invoice.partner_id.vat

        order_reference = SubElement(recipient, 'eb:OrderReference')
        order_id = SubElement(order_reference, 'eb:OrderID')

        # Auftragsreferenz des Bundes
        pattern_ref = "(^[0-9]{10}$|^[0-9]{10}:[A-Za-z0-9]{3}$|^[A-Za-z0-9]{3}$)" #zB.: 4700000001 oder 4700000001:Z01 oder Z01

        # Referenz von Kunden beziehen
        if invoice.partner_id.eb_interface_para == 'group':
            client_order_ref = invoice.partner_id.eb_group.content
        # Referenz aus Rechnung beziehen
        elif invoice.partner_id.eb_interface_para == 'ref':
            client_order_ref = invoice.name
            if not client_order_ref:
                errorMsg = 'Auftragsreferenz zur Bestellung fehlt.\nBitte im Feld Referenz/Beschreibung erfassen.'
                raise Warning(errorMsg)
        else:
            raise Warning('EB Interface - Parameter bei Kunde %s muss \"Gruppe\" oder \"Bestellreferenz\" sein' % invoice.partner_id.name)

        order_id.text = client_order_ref

        self._appendAddress(recipient, invoice.partner_id)

        if not invoice.partner_id.ref:
            errorMsg = 'Kundennummer/Interne Referenz muss bei Partner %s hinterlegt sein' % invoice.partner_id.name
            raise Warning(errorMsg)

        billers_invoice_recipient_id = SubElement(recipient, 'eb:BillersInvoiceRecipientID')
        billers_invoice_recipient_id.text = invoice.partner_id.ref

    def _appendInvoiceLinesAndDownPayments(self, root, invoice):
        details = SubElement(root, 'eb:Details')
        self._appendInvoiceLines(details, invoice)
        # Vorrauszahlungen
        # self._appendDownPaymentLines(details, invoice)

    # e.g. Discounts
    def _appendReductionAndSurchargeDetails(self, root, invoice):
        return

    def _appendInvoiceLines(self, root, invoice):
        itemList = SubElement(root, 'eb:ItemList')

        # Referenz von Kunden beziehen
        if invoice.partner_id.eb_interface_para == 'group':
            client_order_ref = invoice.partner_id.eb_group.content
        # Referenz aus Rechnung beziehen
        elif invoice.partner_id.eb_interface_para == 'ref':
            client_order_ref = invoice.name
            if not client_order_ref:
                errorMsg = 'Auftragsreferenz zur Bestellung fehlt.\nBitte im Feld Referenz/Beschreibung erfassen.'
                raise Warning(errorMsg)
        else:
            raise Warning(
                'EB Interface - Parameter bei Kunde %s muss \"Gruppe\" oder \"Bestellreferenz\" sein' % invoice.partner_id.name)

        order_id = client_order_ref

        pos = 1
        for line in invoice.invoice_line_ids:
            self._appendInvoiceLineItem(itemList, line, order_id, pos)
            pos += 1

    # not used for this project
    def _appendDownPaymentLines(self, root, invoice):
        for payment_line in invoice.account_invoice_payment_lines:
            belowTheLineItem = SubElement(root, 'eb:BelowTheLineItem')
            description = SubElement(belowTheLineItem, 'eb:Description')
            description.text = payment_line.name

            amount = (payment_line.amount + payment_line.amount_tax) * -1
            lineItemAmount = SubElement(belowTheLineItem, 'eb:LineItemAmount')
            lineItemAmount.text = "%.2f" % amount

    # override this method to if some invoice lines should not be appended
    def checkAppendInvoiceLineItem(self, line):
        return True

    # append discounts for invoice line
    def appendDiscounts(self, listLineItem, line):
        # Rabatt123456
        if line.discount > 0.0:
            reduction_and_surcharge_details = SubElement(listLineItem, 'eb:ReductionAndSurchargeListLineItemDetails')
            discount_element = SubElement(reduction_and_surcharge_details, 'eb:ReductionListLineItem')

            # Nettobetrag ohne Rabatt
            base_amount = SubElement(discount_element, 'eb:BaseAmount')
            base_amount.text = "%.2f" % (line.price_unit * line.quantity)

            # Prozentsatz Rabatt
            discount_percentage = SubElement(discount_element, 'eb:Percentage')
            discount_percentage.text = "%.2f" % line.discount

            # Betrag Rabatt
            discount_percentage = SubElement(discount_element, 'eb:Amount')
            discount_percentage.text = "%.2f" % (line.price_unit * line.quantity * (line.discount / 100))


    def _appendInvoiceLineItem(self, root, line, invoice_order_id, pos):
        if not self.checkAppendInvoiceLineItem(line):
            return False

        listLineItem = SubElement(root, 'eb:ListLineItem')

        description = SubElement(listLineItem, 'eb:Description')
        description.text = line.name

        if line.product_id and line.product_id.default_code:
            articleNumber = SubElement(listLineItem, 'eb:ArticleNumber')  # optional
            articleNumber.text = line.product_id.default_code

        attributes = {'eb:Unit': UNIT_TYPE}

        quantity = SubElement(listLineItem, 'eb:Quantity', attrib=attributes)
        quantity.text = str(line.quantity)

        unitPrice = SubElement(listLineItem, 'eb:UnitPrice')
        unitPrice.text = str(line.price_unit)

        if line.invoice_line_tax_ids and len(line.invoice_line_tax_ids) == 1:
            vatRate = SubElement(listLineItem, 'eb:VATRate')
            tax_percentage = line.invoice_line_tax_ids[0].amount
            vatRate.text = "%.2f" % tax_percentage
        elif line.invoice_line_tax_ids and len(line.invoice_line_tax_ids) > 1:
            Warning(u"In der Rechnungszeile mit der Beschreibung %s wurden mehrere Steuersätze angegeben. Pro Rechnungszeile darf nur 1 Steuersatz erfasst werden" % line.name)

        # append discounts for invoice line
        self.appendDiscounts(listLineItem, line)

        invoice_recipients_order_reference = SubElement(listLineItem, 'eb:InvoiceRecipientsOrderReference')

        order_id = SubElement(invoice_recipients_order_reference, 'eb:OrderID')
        order_id.text = invoice_order_id
        order_position_number = SubElement(invoice_recipients_order_reference, 'eb:OrderPositionNumber')
        order_position_number.text = str(pos)


        lineItemAmount = SubElement(listLineItem, 'eb:LineItemAmount')
        lineItemAmount.text = str(line.price_subtotal)

    def _appendTaxes(self, root, invoice):
        tax = SubElement(root, 'eb:Tax')
        vat = SubElement(tax, 'eb:VAT')
        for line in invoice.tax_line_ids:
            item = SubElement(vat, 'eb:VATItem')

            # Betrag Steuerbasis
            taxedAmount = SubElement(item, 'eb:TaxedAmount')
            taxedAmount.text = "%.2f" % line.base

            # Prozentsatz der Steuer
            tax_percentage = 0.0
            tax_amount = line.amount
            if line.base > 0.0:
                tax_percentage = float(tax_amount) / float(line.base) * 100

            taxedRate = SubElement(item, 'eb:VATRate')
            taxedRate.text = "%.0f" % tax_percentage  # rundet berechneten Prozentsatz der Steuer zB 19.96 auf 20

            # Steuerbetrag
            amount = SubElement(item, 'eb:Amount')
            amount.text = "%.2f" % tax_amount

    def _appendTotalGrossAmount(self, root, invoice):
        total_gross_amount = SubElement(root, 'eb:TotalGrossAmount')
        total_gross_amount.text = str(invoice.amount_total)

    def _appendPayableAmount(self, root, invoice):
        payable_ammount = SubElement(root, 'eb:PayableAmount')
        payable_ammount.text = str(invoice.amount_total)

    def _appendPaymentConditions(self, root, invoice):
        if invoice.date_due:
            payment_conditions = SubElement(root, 'eb:PaymentConditions')
            due_date = SubElement(payment_conditions, 'eb:DueDate')
            due_date.text = str(invoice.date_due)

    def _appendPaymentMethod(self, root, invoice):
        payment_method = SubElement(root, 'eb:PaymentMethod')
        attributes = {'eb:ConsolidatorPayable': 'false'}
        universal_bank_transaction = SubElement(payment_method, 'eb:UniversalBankTransaction', attrib=attributes)
        beneficiary_account = SubElement(universal_bank_transaction, 'eb:BeneficiaryAccount')

        company_id = invoice.sudo().company_id
        if invoice.partner_id.eb_bank_id:
            bank = invoice.partner_id.eb_bank_id
            iban_text = bank.acc_number
            bic_text = bank.bank_bic
            bank_name_text = bank.bank_name
            acount_owner_text = company_id.name
        elif company_id and company_id.bank_ids and len(company_id.bank_ids.filtered('bank_for_eb')) > 0:
            bank = company_id.bank_ids.filtered('bank_for_eb')
            iban_text = bank.acc_number
            bic_text = bank.bank_bic
            bank_name_text = bank.bank_name
            acount_owner_text = company_id.name
        else:
            raise Warning("Keine Bank für E-Rechnungsversand definiert.\nKennzeichnen Sie die entsprechnede Bankverbindung in den Unternehmensdaten.")

        bank_name = SubElement(beneficiary_account, 'eb:BankName')
        bank_name.text = bank_name_text

        bic = SubElement(beneficiary_account, 'eb:BIC')
        bic.text = bic_text

        iban = SubElement(beneficiary_account, 'eb:IBAN')
        iban.text = iban_text

        bank_account_owner = SubElement(beneficiary_account, 'eb:BankAccountOwner')
        bank_account_owner.text = acount_owner_text

    def _appendAddress(self, root, partner, customEmail=False):
        address = SubElement(root, 'eb:Address')

        name = SubElement(address, 'eb:Name')
        name.text = partner.name

        errorMsg = None
        if not partner.street:
            errorMsg = 'Strasse bei Partner %s muss hinterlegt sein' % partner.name
        elif not partner.city:
            errorMsg = "Stadt bei Partner %s muss hinterlegt sein" % partner.name
        elif not partner.zip:
            errorMsg = "PLZ bei Partner %s muss hinterlegt sein" % partner.name
        elif not partner.country_id:
            errorMsg = "Land bei Partner %s muss hinterlegt sein" % partner.name
        elif not partner.country_id.code:
            errorMsg = "Länderkürzel für Land % fehlt" % partner.country_id.name

        if errorMsg:
            raise Warning(errorMsg)

        street = SubElement(address, 'eb:Street')
        street.text = partner.street

        town = SubElement(address, 'eb:Town')
        town.text = partner.city

        zip = SubElement(address, 'eb:ZIP')
        zip.text = partner.zip

        country = SubElement(address, 'eb:Country')
        country.text = partner.country_id.code

        if partner.phone:
            phone = SubElement(address, 'eb:Phone')
            phone.text = partner.phone

        if partner.email:
            email = SubElement(address, 'eb:Email')
            if customEmail:
                email.text = customEmail
            else:
                email.text = partner.email
