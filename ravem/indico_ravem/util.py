import requests
from requests.auth import HTTPDigestAuth
from urlparse import urljoin

from indico_ravem.plugin import RavemPlugin


def ravem_api_call(api_endpoint, **kwargs):
    """Emits a call to the given RAVEM API endpoint.

    This function is meant to be used to easily generate calls to the RAVEM API.
    The RAVEM URL, username and password are automatically fetched from the
    settings of the RAVEM plugin each time.

    :param api_endpoint: str -- The RAVEM API endpoint to call.
    :param \*\*kwargs: The field names and values used for the RAVEM API as
    strings

    :returns: :class: requests.models.Response -- The response from the RAVEM
    API usually as a JSON (with an `error` message if the call failed.)
    """
    root_endpoint = RavemPlugin.settings.get('api_endpoint')
    username = RavemPlugin.settings.get('username')
    password = RavemPlugin.settings.get('password')
    headers = {'Accept': 'text/*;q=.5, application/json'}
    try:
        return requests.get(urljoin(root_endpoint, api_endpoint), auth=HTTPDigestAuth(username, password),
                            params=kwargs, verify=False, headers=headers)
    except Exception as e:
        RavemPlugin.logger.exception("Ravem API {0} call not successful: {1}".format(api_endpoint, e.message))
        raise
