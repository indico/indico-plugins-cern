from __future__ import unicode_literals

from setuptools import setup, find_packages


setup(
    name='indico_audiovisual',
    version='0.4',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'indico>=1.9.6'
    ],
    entry_points={
        'indico.plugins': {'audiovisual = indico_audiovisual.plugin:AVRequestsPlugin'},
        'indico.zodb_importers': {'audiovisual = indico_audiovisual.zodbimport:AVRequestsImporter'}
    }
)
