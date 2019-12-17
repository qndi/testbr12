Um den die Unit-Tests laufen zu lassen geht man wie folgt vor. Diese Schritte
sind vollständig für das erste Einrichten. Wenn virtualenv und DB bereits
vorhanden sind, braucht man sie natürlich nicht neu erstellen. Allerdings kann
es sein, daß die Tests nicht mehr funktionieren, wenn durch zusätzliche Daten
Konflikte entstanden sind oder die Ergebnisse geändert werden. In diesem Fall
wird man doch eine neue DB anlegen.

Odoo legt seine Testdaten relativ zum während der Installation aktuellen Datum
an. Dadurch verschieben sich jeden Monat die Wochentage an denen diese
Termine liegen. Wir haben Berechnungen, die vom Wochentag abhängen, deshalb
liegen unsere Testdaten fix im Oktober 2018. Odoo legt die Termine hauptsächlich
in die Nähe des Installationsdatums, es werden aber auch Projektbuchungen ca.
4,5 Monate in der Vergangenheit angelegt. Deshalb kann es vorkommen, daß die
Odoo-Testdaten in unseren Zeitraum fallen und die Ergebnisse verfälschen. Der
Effekt verschwindet im nächsten Monat wieder.

In den Submodulen dürfen nur Testdaten für die eigenen Objekte des Moduls
angelegt werden. Alles andere kommt in dp_hr. Damit wird erreicht, daß die
Tests von dp_hr immer funktionieren, egal welche Submodule installiert sind.

Style-Guide:
In assert-Statements steht der tatsächliche Wert links und der erwartete rechts.

Die Tests sollen auch unter Odoo.sh mit dem Odoo-Standard-Testframework
laufen. Es ist noch nicht klar, ob und wie man dort pytest installieren kann.
Deshalb sollten derweil keine pytest-Features verwendet werden, die explizit
importiert werden müssen. Z. B. sollte anstatt pytest.raises also
self.assertRaisesRegex verwendet werden.

Es werden nur einfache assert-Statements verwendet. Von pytest werden diese
umgeschrieben, um je nach Datentyp Details zu den Unterschieden anzuzeigen.
Auf odoo.sh gibt es diese deshalb nicht, wenn Tests fehlschlagen, wird man
sich das aber ohnehin lokal anschauen wollen.

Wenn es zu einem solchen Fehler kommt:
__ ERROR collecting addons/account_check_printing/tests/test_print_check.py __
/home/cha/.local/share/virtualenvs/demo12e-Hzi_-hNf/lib/python3.5/site-packages/pytest_odoo.py:113: in _importtestmodule
    pkgroot = pypkgpath.dirpath()
E   AttributeError: 'NoneType' object has no attribute 'dirpath'
dann wird wohl in diesem Test etwas importiert, das nicht gefunden wird.


Weitere Informationen stehen in gitrepos/onr-plus/dev/pytest/pytest-odoo.txt.

Im Hauptverzeichnis des Repository muß sich eine Datei pytest.ini mit
folgendem Inhalt befinden:
# pytest 3.8 reports deprecation warnings from the code being tested.
# Odoo produces a lot of them, spoiling the readability of the test
# results. Thus ignore them again.
[pytest]
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning


cd gitrepos/demo12e
pipenv install --dev

pytest-odoo ist in der Dev-Sektion, deshalb müssen diese Pakete mitinstalliert
werden. pytest kommt dann automatisch als Abhängigkeit mit.

Aktuell funktioniert die Kombination pytest 4.0.0 und pytest-odoo 0.4.7. Davor
haben pytest 3.6.2 und pytest-odoo 0.4.2 funktioniert. Dazwischen gab es
Probleme. Wenn nötig, muß man im Pipfile die zu verwendenden Versionen
festlegen.

Server normal starten
DB über den DB-Manager mit Demo-Daten anlegen:
Database Name: demo12e_1
Email: admin
Password: x
Language: German / Deutsch
Coutry: Austria
Demo data: X

Der normale Server wird jetzt nicht mehr benötigt, pytest-odoo startet sich
einen eigenen. Deswegen sind Code-Änderungen ohne weiteres beim nächsten
Testlauf aktiv. Es ist aber evtl. besser den normalen Server während der Tests
zu beenden, damit er nicht auf Änderungen in der DB reagiert, was evtl. zu
Problemen führt.

Odoo-Tests:
Hier gibt es die Tests für den Odoo-Core und separat für die
Enterprise-Addons, falls vorhanden. Der nächste Abschnitt ist für beide
gleich.

Es dürfen nur Tests ausgeführt werden deren Add-ons auch installiert sind,
ansonsten werden sie natürlich nicht funktionieren oder gar steckenbleiben.
Die von pytest beim collect ermittelte Liste muß also entsprechend gefiltert
werden.

Das macht dev/pytest/conftest.py. Es wohnt dort und ist in den Odoo-Core
verlinkt, damit es von pytest gefunden wird. Der Link muß nach einem
Odoo-Upgrade wiederhergestellt werden:
cd ext/odoo/addons
ln -s ../../../dev/pytest/conftest.py
cd -
cd ext/enterprise-addons
ln -s ../../dev/pytest/conftest.py


Um schneller herauszufinden, ob die Liste korrekt ist, kann man die Option
--collect-only verwenden. Damit werden nur die auszuführenden Tests bestimmt,
aber nicht ausgeführt.

Odoo-Core:
Diese Dateien werden von pytest gefunden, sind aber keine Test bzw. die Tests
funktionieren nicht mehr aufgrund unserer Änderungen oder sind aus anderen
Gründen problematisch und werden daher ausgeschlossen.

--ignore=addons/mass_mailing/wizard/test_mailing.py
Das ist ein regulärer Wizard, evtl. für Testzwecke, aber kein Unittest

--ignore=doc
Odoo-Doku, kein relevanter Code

--ignore=odoo/tools/test_config.py
Testskript, aber kein Unittest

--ignore=odoo/tools/test_reports.py
Testskript, aber kein Unittest

--deselect=odoo/addons/base/tests/test_xmlrpc.py
--deselect=addons/web/tests/test_image.py
Der Webserver wird derweil nicht gestartet

--deselect=odoo/addons/base/tests/test_orm.py::TestInherits::test_copy
Test, der fehlschlägt wenn die DB mit einer anderen Sprache als en_US aufgesetzt wird. Als Nebenwirkung wird auch test_copy_with_ancestor deaktiviert, weil sein Name denselben Prefix hat.

--deselect=odoo/addons/base/tests/test_misc.py::TestFormatLangDate::test_00_accepted_types
Test, der wegen des unterschiedlichen Datumsformats fehlschlägt

--ignore=addons/account_check_printing/tests/test_print_check.py
odoo.addons.account kann irgendwie nicht importiert werden. Sollte wohl gehen,
wenn man das löst.


cd gitrepos/demo12e
pipenv shell
cd ext/odoo
export ODOO_RC=/home/cha/gitrepos/demo12e/dev/odoo-server-pytest-odoo.conf
export ODOO_DSN=dbname=demo12e_1
export PYTHONPATH=/home/cha/gitrepos/demo12e/ext/odoo

pytest --odoo-database=demo12e_1 --rootdir=`pwd` <--ignore und --deselect von oben>


Enterprise-Addons:
cd gitrepos/demo12e
pipenv shell
cd ext/odoo
export ODOO_RC=/home/cha/gitrepos/demo12e/dev/odoo-server-pytest-odoo.conf
export ODOO_DSN=dbname=demo12e_1
export PYTHONPATH=/home/cha/gitrepos/demo12e/ext/odoo

pytest --odoo-database=demo12e_1 --rootdir=`pwd` ../enterprise-addons


Modul-Tests:
cd gitrepos/demo12e
pipenv shell
export ODOO_RC=/home/cha/gitrepos/demo12e/dev/odoo-server-dev-ha.conf
export PYTHONPATH=/home/cha/gitrepos/demo12e/ext/odoo

pytest --odoo-database=demo12e_1 ../dp-apps/dp_hr
