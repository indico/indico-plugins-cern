from __future__ import unicode_literals

from datetime import timedelta

import os

from flask import g, flash
from flask_pluginengine import render_plugin_template
from wtforms.fields.core import BooleanField
from wtforms.fields.html5 import URLField
from wtforms.validators import DataRequired

from indico.core import signals
from indico.core.plugins import IndicoPlugin
from indico.modules.attachments.forms import AddAttachmentFilesForm
from indico.modules.attachments.models.attachments import AttachmentType
from indico.util.date_time import now_utc
from indico.web.forms.base import IndicoForm
from indico.web.forms.fields import TextListField
from indico.web.forms.widgets import SwitchWidget
from MaKaC.webinterface.pages.conferences import WPTPLConferenceDisplay

from indico_conversion import _, cache
from indico_conversion.blueprint import blueprint
from indico_conversion.conversion import submit_attachment
from indico_conversion.util import get_pdf_title


info_ttl = timedelta(hours=1)


class SettingsForm(IndicoForm):
    server_url = URLField(_('Server URL'), [DataRequired()],
                          description=_("The URL to the conversion server's getSegFile.py script."))
    valid_extensions = TextListField(_('Extensions'),
                                     filters=[lambda exts: sorted({ext.lower().lstrip('.').strip() for ext in exts})],
                                     description=_('File extensions for which PDF conversion is supported. '
                                                   'One extension per line.'))


class ConversionPlugin(IndicoPlugin):
    """PDF Conversion

    Provides PDF conversion for materials
    """
    configurable = True
    settings_form = SettingsForm
    default_settings = {'server_url': 'http://conversion.cern.ch/getSegFile.py',
                        'valid_extensions': ['ppt', 'doc', 'pptx', 'docx', 'odp', 'sxi']}
    strict_settings = True

    def init(self):
        super(ConversionPlugin, self).init()
        self.connect(signals.add_form_fields, self._add_form_fields, sender=AddAttachmentFilesForm)
        self.connect(signals.form_validated, self._form_validated)
        self.connect(signals.attachments.attachment_created, self._attachment_created)
        self.template_hook('event-display-after-attachment', self._event_display_after_attachment)
        self.inject_css('conversion_css', WPTPLConferenceDisplay)

    def get_blueprints(self):
        return blueprint

    def register_assets(self):
        self.register_css_bundle('conversion_css', 'css/conversion.scss')

    def _add_form_fields(self, form_cls, **kwargs):
        exts = ', '.join(self.settings.get('valid_extensions'))
        return 'convert_to_pdf', \
               BooleanField(_("Convert to PDF"), widget=SwitchWidget(),
                            description=_("If enabled, your files will be be converted to PDF if possible. "
                                          "The following file types can be converted: {exts}").format(exts=exts),
                            default=True)

    def _form_validated(self, form, **kwargs):
        if not isinstance(form, AddAttachmentFilesForm):
            return
        g.convert_attachments_pdf = form.ext__convert_to_pdf.data

    def _attachment_created(self, attachment, **kwargs):
        if not g.get('convert_attachments_pdf') or attachment.type != AttachmentType.file:
            return
        ext = os.path.splitext(attachment.file.filename)[1].lstrip('.')
        if ext not in self.settings.get('valid_extensions'):
            return
        submit_attachment.delay(attachment)
        cache.set(unicode(attachment.id), True, info_ttl)
        flash(_('{file} has been sent to the conversion system. The PDF file will be attached automatically once '
                'the conversion finished.').format(file=attachment.file.filename))

    def _event_display_after_attachment(self, attachment, top_level, **kwargs):
        if attachment.type != AttachmentType.file:
            return None
        if now_utc() - attachment.file.created_dt > info_ttl:
            return None
        if not cache.get(unicode(attachment.id)):
            return None
        return render_plugin_template('pdf_attachment.html', attachment=attachment, top_level=top_level,
                                      title=get_pdf_title(attachment))
