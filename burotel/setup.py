from __future__ import unicode_literals

from setuptools import setup


setup(
    name='indico-plugin-burotel',
    version='1.0',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    py_modules=('indico_burotel',),
    zip_safe=False,
    install_requires=[
        'indico>=2.0a1'
    ],
    entry_points={
        'indico.plugins': {'burotel = indico_burotel:BurotelPlugin'}
    }
)
