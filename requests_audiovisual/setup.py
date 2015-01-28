from __future__ import unicode_literals

from setuptools import setup, find_packages


setup(
    name='indico_requests_audiovisual',
    version='0.1',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'indico>=1.9.1'
    ],
    entry_points={
        'indico.plugins': {'requests_audiovisual = indico_requests_audiovisual.plugin:AVRequestsPlugin'},
        'indico.zodb_importers': {'requests_audiovisual = indico_requests_audiovisual.zodbimport:AVRequestsImporter'}
    }
)
