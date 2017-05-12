from __future__ import unicode_literals

from setuptools import setup, find_packages


setup(
    name='indico_audiovisual',
    version='0.4.1',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        'indico>=1.9.11.dev1'
    ],
    entry_points={
        'indico.plugins': {'audiovisual = indico_audiovisual.plugin:AVRequestsPlugin'},
        'indico.zodb_importers': {'audiovisual = indico_audiovisual.zodbimport:AVRequestsImporter'}
    }
)
