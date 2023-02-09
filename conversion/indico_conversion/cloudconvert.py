# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2022 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

import requests


endpoints = {
    'live': 'https://api.cloudconvert.com/v2',
    'sandbox': 'https://api.sandbox.cloudconvert.com/v2',
    'user': 'https://api.cloudconvert.com/v2/users/me'
}


class Resource:
    resource = None

    def __init__(self, api_client):
        self.api_client = api_client

    def find(self, id):
        url = f'{self.api_client.endpoint}/{self.resource}/{id}'
        response = requests.get(url, headers=self.api_client.headers)
        return self._process_response(response)

    def create(self, payload):
        url = f'{self.api_client.endpoint}/{self.resource}'
        response = requests.post(url, json=payload, headers=self.api_client.headers)
        return self._process_response(response)

    def _process_response(self, response):
        response.raise_for_status()
        json = response.json()
        return json.get('data', json)


class Job(Resource):
    resource = 'jobs'


class Task(Resource):
    resource = 'tasks'

    def upload(self, task, file):
        if task['operation'] != 'import/upload':
            raise Exception("The task operation is not import/upload")

        form = task['result']['form']
        with file.open() as fd:
            response = requests.post(url=form['url'], files={'file': fd}, data=form['parameters'])
            response.raise_for_status()
            if response.status_code != 201:
                raise requests.RequestException(f'Unexpected response status from server: {response.status_code}',
                                                response=response)


class CloudConvertRestClient:
    def __init__(self, *, api_key=None, sandbox=False):
        self.api_key = api_key
        self.sandbox = sandbox
        self.Job = Job(self)
        self.Task = Task(self)

    @property
    def endpoint(self):
        return endpoints['sandbox' if self.sandbox else 'live']

    @property
    def headers(self):
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def get_remaining_credits(self):
        response = requests.get(endpoints['user'], headers=self.headers)
        response.raise_for_status()
        return response.json()['data']['credits']
