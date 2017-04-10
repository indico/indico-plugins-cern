from __future__ import unicode_literals


from setuptools import setup, find_packages


setup(
    name='indico_search_cern',
    version='0.1',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'indico>=1.9.10',
        'indico_search'
    ],
    entry_points={'indico.plugins': {'search_cern = indico_search_cern.plugin:CERNSearchPlugin'},
                  'indico.zodb_importers': {'search_cern = indico_search_cern.zodbimport:CERNSearchImporter'}}
)
