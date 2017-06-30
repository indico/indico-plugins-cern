from __future__ import unicode_literals

from setuptools import setup


setup(
    name='indico_foundationsync',
    version='1.0.5.dev0',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    py_modules=('indico_foundationsync',),
    zip_safe=False,
    install_requires=[
        'indico>=2.0.dev0',
        'cx_Oracle',
    ],
    entry_points={
        'indico.plugins': {'foundationsync = indico_foundationsync:FoundationSyncPlugin'}
    }
)
