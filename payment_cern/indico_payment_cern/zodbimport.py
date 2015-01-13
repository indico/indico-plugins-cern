from __future__ import unicode_literals

from indico.core.db import db
from indico.util.console import cformat
from indico_zodbimport import Importer, convert_to_unicode

from indico_payment_cern.plugin import CERNPaymentPlugin


class CERNPaymentImporter(Importer):
    plugins = {'payment_cern'}

    def migrate(self):
        self.migrate_settings()

    def migrate_settings(self):
        print cformat('%{white!}migrating settings')
        payment_method_map = {
            'name': 'name',
            'displayName': 'title',
            'type': 'type',
            'extraFee': 'fee'
        }
        settings_map = {
            'FPEmaillAddress': 'fp_email_address',
            'FPDepartmentName': 'fp_department_name',
            'paymentURL': 'payment_url',
            'shopID': 'shop_id',
            'hashSeed': 'hash_seed',
            'hashSeedOut': 'hash_seed_out',
            'serverURLSuffix': 'server_url_suffix',
            'orderIDPrefix': 'order_id_prefix'
        }
        CERNPaymentPlugin.settings.delete_all()
        opts = self.zodb_root['plugins']['EPayment']._PluginType__plugins['CERNYellowPay']._PluginBase__options
        # Migrate payment methods
        payment_methods = [{new: pm[old] for old, new in payment_method_map.iteritems()}
                           for pm in opts['paymentMethods'].getValue()]
        CERNPaymentPlugin.settings.set('payment_methods', payment_methods)
        # Migrate other options
        for old, new in settings_map.iteritems():
            value = opts[old].getValue()
            if isinstance(value, basestring):
                value = convert_to_unicode(value).strip()
            CERNPaymentPlugin.settings.set(new, value)
        db.session.commit()
