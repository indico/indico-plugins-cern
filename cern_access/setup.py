from __future__ import unicode_literals

from setuptools import find_packages, setup


setup(
    name='indico-plugin-cern-access',
    version='1.0.dev0',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'indico>=2.0a2'
    ],
    entry_points={
        'indico.plugins': {'cern_access = indico_cern_access.plugin:CERNAccessPlugin'}
    }
)
