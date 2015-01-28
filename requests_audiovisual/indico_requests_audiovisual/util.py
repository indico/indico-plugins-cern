from __future__ import unicode_literals

from indico.util.user import retrieve_principals


def is_av_manager(user):
    """Checks if a user is an AV manager"""
    from indico_requests_audiovisual.plugin import AVRequestsPlugin
    principals = retrieve_principals(AVRequestsPlugin.settings.get('managers'))
    return any(principal.containsUser(user) for principal in principals)
