from __future__ import unicode_literals

from setuptools import setup, find_packages


setup(
    name='indico_custom_themes',
    version='0.1.2',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=['indico>=1.9.11.dev2'],
    entry_points={'indico.plugins': {'themes_cern = indico_custom_themes.plugins:CERNThemesPlugin',
                                     'themes_lcagenda = indico_custom_themes.plugins:LCAgendaThemesPlugin'}}
)
