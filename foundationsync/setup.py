# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2019 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from setuptools import setup


setup(
    name='indico-plugin-foundationsync',
    version='2.2',
    url='https://github.com/indico/indico-plugins-cern',
    license='MIT',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    py_modules=('indico_foundationsync',),
    zip_safe=False,
    install_requires=[
        'indico>=2.2.dev0',
        'cx_Oracle',
    ],
    entry_points={
        'indico.plugins': {'foundationsync = indico_foundationsync:FoundationSyncPlugin'}
    },
    classifiers=[
        'Environment :: Plugins',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
    ],
)
