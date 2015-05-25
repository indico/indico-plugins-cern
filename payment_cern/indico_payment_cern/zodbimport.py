from __future__ import unicode_literals

from indico.core.db import db
from indico.modules.events.models.settings import EventSetting
from indico.util.console import cformat
from indico.util.struct.iterables import committing_iterator
from indico_zodbimport import Importer, convert_to_unicode

from indico_payment_cern.plugin import CERNPaymentPlugin


class CERNPaymentImporter(Importer):
    plugins = {'payment_cern'}

    def migrate(self):
        self.migrate_settings()
        self.migrate_event_settings()

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
            'shopID': 'shop_id_chf',
            'hashSeed': 'hash_seed_chf',
            'hashSeedOut': 'hash_seed_out_chf',
            'serverURLSuffix': 'server_url_suffix',
            'orderIDPrefix': 'order_id_prefix'
        }
        CERNPaymentPlugin.settings.delete_all()
        opts = self.zodb_root['plugins']['EPayment']._PluginType__plugins['CERNYellowPay']._PluginBase__options
        # Migrate payment methods
        payment_methods = [{new: pm[old] for old, new in payment_method_map.iteritems()}
                           for pm in opts['paymentMethods']._PluginOption__value]
        CERNPaymentPlugin.settings.set('payment_methods', payment_methods)
        # Migrate other options
        for old, new in settings_map.iteritems():
            value = opts[old]._PluginOption__value
            if isinstance(value, basestring):
                value = convert_to_unicode(value).strip()
            CERNPaymentPlugin.settings.set(new, value)
        db.session.commit()

    def migrate_event_settings(self):
        print cformat('%{white!}migrating event settings')
        default_fees = {m['name']: float(m['fee']) for m in CERNPaymentPlugin.settings.get('payment_methods')}
        default_method_name = CERNPaymentPlugin.settings.get('method_name')
        EventSetting.delete_all(CERNPaymentPlugin.event_settings.module)
        for event in committing_iterator(self._iter_events(), 25):
            yp = event._modPay.payMods['CERNYellowPay']
            # Migrate basic settings
            CERNPaymentPlugin.event_settings.set(event, 'enabled', True)
            method_name = convert_to_unicode(yp._title)
            if method_name in {'CERN Epayment', 'CERNYellowPay'}:
                method_name = default_method_name
            CERNPaymentPlugin.event_settings.set(event, 'method_name', method_name)
            # Migrate payment fees
            no_fee_data = False
            apply_fees = getattr(yp, '_applyFee', True)
            if (not hasattr(yp, '_paymentMethodList') or
                    any(isinstance(x, bool) for x in yp._paymentMethodList.itervalues())):
                # some old events don't have the payment method fee data; we assume no fees in that case
                no_fee_data = True
                apply_fees = False
            CERNPaymentPlugin.event_settings.set(event, 'apply_fees', apply_fees)
            custom_fees = None
            if not no_fee_data:
                old_methods = yp._paymentMethodList
                custom_fees = {method: {'fee': unicode(old_methods[method]._extraFee)}
                               for method, fee in default_fees.iteritems()
                               if method in old_methods and float(old_methods[method]._extraFee) != fee}
                if custom_fees:
                    CERNPaymentPlugin.event_settings.set(event, 'custom_fees', custom_fees)

            print cformat(' - %{cyan}event {} (fees: {}, custom fees: {})').format(event.id, apply_fees, custom_fees)
            if no_fee_data:
                print cformat('   %{yellow}no payment method fee information')

    def _iter_events(self):
        for event in self.flushing_iterator(self.zodb_root['conferences'].itervalues()):
            # Skip events where epayment is not enabled
            if not hasattr(event, '_modPay') or not event._modPay.activated:
                continue
            # Skip events where cern epayment is not present
            if 'CERNYellowPay' not in event._modPay.payMods:
                continue
            # Skip events where cern epayment is disabled
            if not event._modPay.payMods['CERNYellowPay']._enabled:
                continue
            yield event
