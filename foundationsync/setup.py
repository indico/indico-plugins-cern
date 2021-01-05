# This file is part of the CERN Indico plugins.
# Copyright (C) 2014 - 2021 CERN
#
# The CERN Indico plugins are free software; you can redistribute
# them and/or modify them under the terms of the MIT License; see
# the LICENSE file for more details.

from setuptools import find_packages, setup


setup(
    name='indico-plugin-foundationsync',
    version='3.0-dev',
    url='https://github.com/indico/indico-plugins-cern',
    license='MIT',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    install_requires=[
        'indico>=3.0.dev0',
        'cx_Oracle>=8.0.1,<9',
    ],
    python_requires='~=3.9',
    entry_points={
        'indico.plugins': {'foundationsync = indico_foundationsync.plugin:FoundationSyncPlugin'}
    },
    classifiers=[
        'Environment :: Plugins',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.9',
    ],
)
