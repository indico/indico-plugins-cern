# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import re
from pprint import pformat
from urlparse import urljoin

import requests
from flask import request, session
from requests.auth import HTTPDigestAuth
from requests.exceptions import HTTPError, Timeout

from indico.util.i18n import _

from indico_ravem.plugin import RavemPlugin
from indico_vc_vidyo.util import retrieve_principal


def ravem_api_call(api_endpoint, method='GET', **kwargs):
    """Emits a call to the given RAVEM API endpoint.

    This function is meant to be used to easily generate calls to the RAVEM API.
    The RAVEM URL, username and password are automatically fetched from the
    settings of the RAVEM plugin each time.

    :param api_endpoint: str -- The RAVEM API endpoint to call.
    :param method: str -- The HTTP method to use for the call, currently, RAVEM
                   only supports `GET` or `POST`
    :param kwargs: The field names and values used for the RAVEM API as
                     strings

    :returns: dict -- The JSON-encoded response from the RAVEM
    :raises: HTTPError if the request returns an HTTP Error (400 or 500)
    :raises: RavemAPIException if RAVEM returns an error message
    """

    root_endpoint = RavemPlugin.settings.get('api_endpoint')
    access_token = RavemPlugin.settings.get('access_token')
    headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer %s' % access_token,
    }
    timeout = RavemPlugin.settings.get('timeout') or None
    url = urljoin(root_endpoint, api_endpoint)

    if RavemPlugin.settings.get('debug') and method != 'GET':
        RavemPlugin.logger.debug('API call:\nURL: %s\nData: %s', url, pformat(kwargs))
        raise RavemAPIException('Action not possible in debug mode', api_endpoint, None)

    try:
        response = requests.request(method, url, headers=headers, timeout=timeout, **kwargs)
    except Timeout as error:
        RavemPlugin.logger.warning("%s %s timed out: %s", error.request.method, error.request.url, error.message)
        # request timeout sometime has an inner timeout error as message instead of a string.
        raise Timeout(_("Timeout while contacting the room."))
    except Exception as error:
        RavemPlugin.logger.exception("failed call: %s %s with %s: %s",
                                     method.upper(), api_endpoint, kwargs, error.message)
        raise

    try:
        response.raise_for_status()
    except HTTPError as error:
        RavemPlugin.logger.exception("%s %s failed with %s", response.request.method, response.url, error.message)
        raise

    return response.json()


def has_access(event_vc_room, _split_re=re.compile(r'[\s,;]+')):
    """Returns whether the current session has access to the RAVEM button.

    To have access, the current user needs to be either the owner of the VC room
    or authorised to modify the event.
    If not the only way to have access is for the request to come from the
    terminal located in the room concerned.

    Note that if the room does not have equipment supported by Vidyo, the access
    will always be refused regardless of the user or the origin of the request.
    """
    link_object = event_vc_room.link_object

    if not link_object:
        return False

    room = link_object.room
    vc_room = event_vc_room.vc_room
    event = event_vc_room.event
    current_user = session.user

    # No physical room or room is not Vidyo capable
    # TODO: We don't have any for zoom yet
    # if not room or not room.has_equipment('Vidyo'):
    #     return False
    if not room:
        return False

    ips = set(filter(None, (x.strip() for x in _split_re.split(room.get_attribute_value('ip', '')))))
    # Not all providers use the same attribute for the principal, some may use owner or host
    host = next(vc_room.data.get(attr) for attr in ('owner', 'host') if attr in vc_room.data)
    if not host:
        raise AttributeError('Unsupported principal attribute (valid: owner or host)')
    return any([
        current_user == retrieve_principal(host),
        event.can_manage(current_user),
        request.remote_addr in ips
    ])


class RavemException(Exception):
    pass


class RavemOperationException(RavemException):
    """Indicates an operation failed and the cause of the failure is known.

    Known causes of failure are for example if the room is already disconnected
    when trying to disconnect it.

    If this exception is raised, make sure to check the `reason` attribute.
    Functions raising this exception should document the possible reasons with
    which the exception can be raised.
    """
    def __init__(self, message, reason):
        super(RavemOperationException, self).__init__(message)
        self.message = message
        self.reason = reason


class RavemAPIException(RavemException):
    """Indicates the RAVEM API replied with an invalid response.

    In this context, by invalid response we mean a valid json response which
    does not match the excepted format of having a `error` or `result` key.
    """
    def __init__(self, message, endpoint, response):
        super(RavemAPIException, self).__init__(message)
        self.message = message
        self.endpoint = endpoint
        self.response = response
