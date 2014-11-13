from __future__ import unicode_literals

from setuptools import setup, find_packages


setup(
    name='indico_livesync_cern',
    version='0.1',
    url='https://gitlab.cern.ch/indico/indico-plugin-livesync-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'indico>=1.9.1',
        'indico_livesync'
    ],
    entry_points={'indico.plugins': {'livesync_cern = indico_livesync_cern.plugin:LiveSyncCERNPlugin'}}
)
