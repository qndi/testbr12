======================
datenpol E-Rechnung
======================
| Rechnungen an die Bundesverwaltung können ausschließlich in elektronischer, strukturierter Form eingebracht werden.
| **Mit diesem Modul können Sie Ihre e-Rechnung einfach und schnell an den Bund übermitteln.**
|
| Damit Sie Ihre e-Rechnungen bei der öffentlichen Verwaltung einbringen können,
| ist zunächst eine Registrierung am Unternehmensserviceportal (USP - www.usp.gv.at) erforderlich.
| Eine Step by Step–Anleitung zur Registrierung am USP ist unter folgendem Link abrufbar: http://www.e-rechnung.gv.at/go/usp_registration

Weitere Informationen zur E-Rechnung finden sie unter https://www.erechnung.gv.at/erb

.. image:: /dp_e_invoice/static/description/e_rechnung_logo.png
  :alt: E-Rechnung diesem Modul können Sie Rechnungen aus Odoo in elektronischer Form direkt an die Bundesverwaltung senden.


Konfiguration Systemparameter
=============================
* | Durch die Registrierung im Unternehmensserviceportal erhalten sie die erforderlichen Zugangsdaten,
  | die sie in den Systemparamtern hinterlegen müssen.
  | Die Systemparameter finden Sie unter **"Einstellungen/Technisch/Systemparameter"**.
  | Dieses Menü wird nur Benutzern mit **Administratorrechten im Debugmodus angezeigt**.
  |
* | Folgende Parameter sind für die E-Rechnung zu konfigurieren:
  | - e_invoice.username (Ihr Benutzername)
  | - e_invoice.password (Ihr Passwort)
  | - e_invoice.response_email (Emailadresse auf der sie eine Rückmeldung nach der Einbringung der E-Rechnung erhalten möchten)
  | - e_invoice.invoice_recipient_biller_id (Ihre Zahlungsempfänger ID)

Konfiguration für Produktivbetrieb
==================================
* Das E-Rechnungsmodul übermittelt die Rechnung im Standard an den Testservice der Bundesverwaltung
* Beim Starten lädt Odoo ein Konfigurationsfile. Für den Produktivbetrieb müssen sie in diesem **Konfigurationfile**
  den Parameter "**environment = PROD**" setzen.

| **Beispiel - Odoo Startbefehl**
| Der Pfad zum Konfigurationsskript wird beim Start von Odoo mit dem Parameter -c angegeben

.. image:: /dp_e_invoice/static/description/path_config_file.jpg
  :alt: Pfad der Odoo Konfigurationsdatei
|
| **Beispiel - Setzen der environment Variable**

.. image:: /dp_e_invoice/static/description/environment_in_config.jpg
  :alt: Umgebungvariable in der Konfigurationsdatei

Konfiguration Bankkonto
=======================
* Der E-Rechnungsservice benötigt neben der Ausgangsrechnung auch noch ihre Bankverbindung
* Diese können sie unter **"Einstellungen/Allgmeine Einstellungen/Konfigurieren Sie Ihre Unternehmensdaten"** erfassen.
* Beachten Sie dass sie beim Konto, dass an den E-Rechnungsservice übermittelt werden soll, die **Checkbox "Bank für EB"** aktiviert ist.

| **Beispiel - Bankverbindung in Unternehmensdaten**

.. image:: /dp_e_invoice/static/description/example_bank_account.jpg
  :alt: Beispiel E-Rechnungskunde

Konfiguration Kunden
====================
* | Nach dem Sie das e-Rechnungs Modul installiert haben, kann der Verkäufer beim Kunden
  | das **Feld "EB Interface – Parameter"** mit den Werten **"Gruppe"** oder **"Bestellreferenz"** befüllen.
* | Wenn das Feld "EB Interface – Parameter" mit "Gruppe" befüllt ist,
  | kann der Verkäufer in einem weiteren Feld die Gruppe spezifizieren.
  | Das Feld "EB Gruppe" wird nur angezeigt, wenn im Feld "EB Interface – Parameter" "Gruppe" eingetragen ist.
  | Dem Verkäufer werden hier alle aktiven EB Gruppen angezeigt und diese können auch ausgewählt werden.
  | Es können ebenfalls neue EB-Gruppen angelegt, bestehende Gruppen bearbeitet und nicht mehr verwendete Gruppen auf inaktiv gesetzt werden.
  | **unter: Abrechnung/Konfiguration/Finanzen/EB Gruppen**
  | Das Objekt EB-Gruppe hat 3 Felder, durch welche eine Zuordnung der Gruppen zu den Kunden erfolgen kann: Inhalt, Bezeichnung (2 Freitextfelder), aktiv (flag).
* | Soll statt der EB Gruppe des Kunden die Bestellreferenz der Rechnung übermittelt werden,
  | so wählen Sie beim **Kunden** die **Option "Bestellreferenz"** und erfassen die Bestellreferenz in der **Rechnung im Feld "Referenz/Beschreibung"**

| **Beispiel - E-Rechnungskunde**

.. image:: /dp_e_invoice/static/description/example_e_invoice_customer.jpg
  :alt: Beispiel E-Rechnungskunde

Verwendung
==========
* Ist beim Kunden das Feld "EB Interface – Parameter" befüllt ist,
  wird in der **Ausgangsrechnung** statt dem „Drucken“ und „Per E-Mail versenden“ Button der **Button "E-Rechnung abschicken"** angezeigt.
* In der Rechnung muss ein **Leistungszeitraum** erfasst werden.
* Sobald die Konfiguration fertig ist, kann die e-Rechnung per Knopfdruck an den Bund übermittelt werden.
* Bevor die Rechnung an den Bund übermittelt wird, wird ihnen ein Dialog angezeigt, in dem sie die Möglichkeit haben mit der Rechnung bis zu 5 Anhänge zu übertragen.
* Der Versand der E-Rechnung wird im Chatter der Ausgangrechnung protokolliert. Die übermittelten Daten werden als Attachment zur Rechnung angehängt.
* Im Druck Menü haben sie weiterhin die Möglichkeit ein PDF zu erzeugen.
|
|
| **Beispiel - Ausgangsrechung**

.. image:: /dp_e_invoice/static/description/example_invoice.jpg
  :alt: Beispiel Ausgangsrechnung
|
|
| **Dialog zum optionalen Versand von bis zu 5 Dateien**

.. image:: /dp_e_invoice/static/description/example_attachment_dialog.jpg
  :alt: Dialog zusätzlicher Dateiversand
|
|
| **Hinweis nach Versand**

.. image:: /dp_e_invoice/static/description/example_notification.jpg
  :alt: Beispiel Notification
|
|
| **Beispiel - Log zur Ausgangsrechnung**

.. image:: /dp_e_invoice/static/description/example_chatter.jpg
  :alt: Beispiel Log im Chatter
