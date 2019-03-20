# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2018 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from __future__ import unicode_literals

from setuptools import setup, find_packages


setup(
    name='indico-plugin-burotel',
    version='3.0-dev',
    url='https://github.com/indico/indico-plugins-cern',
    license='MIT',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'indico>=2.2.dev0'
    ],
    entry_points={
        'indico.plugins': {'burotel = indico_burotel.plugin:BurotelPlugin'}
    },
    classifiers=[
        'Environment :: Plugins',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
    ],
)
