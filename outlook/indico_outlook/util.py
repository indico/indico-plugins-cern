from __future__ import unicode_literals


def check_config():
    """Checks if all required config options are set"""
    from indico_outlook.plugin import OutlookPlugin

    settings = OutlookPlugin.settings.get_all()
    return all(settings[x] for x in ('service_url', 'username', 'password'))
