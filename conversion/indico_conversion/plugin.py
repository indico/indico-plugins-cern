# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2023 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import os
from datetime import timedelta

from flask import flash, g
from flask_pluginengine import render_plugin_template, uses
from wtforms.fields import BooleanField, EmailField, IntegerField, URLField
from wtforms.validators import DataRequired, NumberRange, Optional

from indico.core import signals
from indico.core.plugins import IndicoPlugin, plugin_engine, url_for_plugin
from indico.modules.attachments.forms import AddAttachmentFilesForm
from indico.modules.attachments.models.attachments import AttachmentType
from indico.modules.events.views import WPSimpleEventDisplay
from indico.util.date_time import now_utc
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import IndicoPasswordField, TextListField
from indico.web.forms.validators import HiddenUnless
from indico.web.forms.widgets import SwitchWidget

from indico_conversion import _, pdf_state_cache
from indico_conversion.blueprint import blueprint
from indico_conversion.conversion import submit_attachment_cloudconvert, submit_attachment_doconverter
from indico_conversion.util import get_pdf_title


info_ttl = timedelta(hours=1)


class SettingsForm(IndicoForm):
    maintenance = BooleanField(_('Maintenance'), widget=SwitchWidget(),
                               description=_('Temporarily disable submitting files. The tasks will be kept and once '
                                             'this setting is disabled the files will be submitted.'))
    use_cloudconvert = BooleanField(_('Use CloudConvert'), widget=SwitchWidget(),
                                    description=_('Use Cloudconvert instead of Doconverter for public materials'))
    server_url = URLField(_('Doconverter server URL'), [DataRequired()],
                          description=_("The URL to the conversion server's uploadFile.py script."))
    cloudconvert_api_key = IndicoPasswordField(_('CloudConvert API key'),
                                               [DataRequired(), HiddenUnless('use_cloudconvert', preserve_data=True)],
                                               toggle=True)
    cloudconvert_sandbox = BooleanField(_('Sandbox'),
                                        [HiddenUnless('use_cloudconvert', preserve_data=True)],
                                        widget=SwitchWidget(),
                                        description=_('Use CloudConvert sandbox'))
    cloudconvert_notify_threshold = IntegerField(_('CloudConvert credit threshold'),
                                                 [Optional(), NumberRange(min=0), HiddenUnless('use_cloudconvert',
                                                                                               preserve_data=True)],
                                                 description=_('Send an email when credits drop below this threshold'))
    cloudconvert_notify_email = EmailField(_('Notification email'), [HiddenUnless('use_cloudconvert',
                                                                                  preserve_data=True)],
                                           description=_('Email to send the notifications to'))
    valid_extensions = TextListField(_('Extensions'),
                                     filters=[lambda exts: sorted({ext.lower().lstrip('.').strip() for ext in exts})],
                                     description=_('File extensions for which PDF conversion is supported. '
                                                   'One extension per line.'))


@uses('owncloud')
class ConversionPlugin(IndicoPlugin):
    """PDF Conversion

    Provides PDF conversion for materials
    """
    configurable = True
    settings_form = SettingsForm
    default_settings = {'use_cloudconvert': False,
                        'maintenance': False,
                        'server_url': '',
                        'cloudconvert_api_key': '',
                        'cloudconvert_sandbox': False,
                        'cloudconvert_notify_threshold': None,
                        'cloudconvert_notify_email': '',
                        'valid_extensions': ['ppt', 'doc', 'pptx', 'docx', 'odp', 'sxi']}

    def init(self):
        super().init()
        self.connect(signals.core.add_form_fields, self._add_form_fields, sender=AddAttachmentFilesForm)
        if plugin_engine.has_plugin('owncloud'):
            from indico_owncloud.forms import AddAttachmentOwncloudForm
            self.connect(signals.core.add_form_fields, self._add_form_fields, sender=AddAttachmentOwncloudForm)
        self.connect(signals.core.form_validated, self._form_validated)
        self.connect(signals.attachments.attachment_created, self._attachment_created)
        self.connect(signals.core.after_commit, self._after_commit)
        self.template_hook('event-display-after-attachment', self._event_display_after_attachment)
        self.inject_bundle('main.css', WPSimpleEventDisplay)
        self.inject_bundle('main.js', WPSimpleEventDisplay)

    def get_blueprints(self):
        return blueprint

    def get_vars_js(self):
        return {'urls': {'check': url_for_plugin('conversion.check')}}

    def _add_form_fields(self, form_cls, **kwargs):
        exts = ', '.join(self.settings.get('valid_extensions'))
        return 'convert_to_pdf', \
               BooleanField(_('Convert to PDF'), widget=SwitchWidget(),
                            description=_('If enabled, your files will be be converted to PDF if possible. '
                                          'The following file types can be converted: {exts}').format(exts=exts),
                            default=True)

    def _form_validated(self, form, **kwargs):
        classes = [AddAttachmentFilesForm]
        if plugin_engine.has_plugin('owncloud'):
            from indico_owncloud.forms import AddAttachmentOwncloudForm
            classes.append(AddAttachmentOwncloudForm)
        if not isinstance(form, tuple(classes)):
            return
        g.convert_attachments_pdf = form.ext__convert_to_pdf.data

    def _attachment_created(self, attachment, **kwargs):
        if not g.get('convert_attachments_pdf') or attachment.type != AttachmentType.file:
            return
        ext = os.path.splitext(attachment.file.filename)[1].lstrip('.').lower()
        if ext not in self.settings.get('valid_extensions'):
            return
        # Prepare for submission (after commit)
        if 'convert_attachments' not in g:
            g.convert_attachments = set()
        g.convert_attachments.add((attachment, attachment.is_protected))
        # Set cache entry to show the pending attachment
        pdf_state_cache.set(str(attachment.id), 'pending', timeout=info_ttl)
        if not g.get('attachment_conversion_msg_displayed'):
            g.attachment_conversion_msg_displayed = True
            flash(_('Your file(s) have been sent to the conversion system. The PDF file(s) will be attached '
                    'automatically once the conversion finished.').format(file=attachment.file.filename))

    def _after_commit(self, sender, **kwargs):
        for attachment, is_protected in g.get('convert_attachments', ()):
            if self.settings.get('use_cloudconvert') and not is_protected:
                submit_attachment_cloudconvert.delay(attachment)
            else:
                submit_attachment_doconverter.delay(attachment)

    def _event_display_after_attachment(self, attachment, top_level, has_label, **kwargs):
        if attachment.type != AttachmentType.file:
            return None
        if now_utc() - attachment.file.created_dt > info_ttl:
            return None
        if pdf_state_cache.get(str(attachment.id)) != 'pending':
            return None
        return render_plugin_template('pdf_attachment.html', attachment=attachment, top_level=top_level,
                                      has_label=has_label, title=get_pdf_title(attachment))
