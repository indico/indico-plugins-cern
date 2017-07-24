from __future__ import unicode_literals

from indico.core import signals
from indico.util.i18n import make_bound_gettext

_ = make_bound_gettext('cern_access')


@signals.import_tasks.connect
def _import_tasks(sender, **kwargs):
    import indico_cern_access.task
