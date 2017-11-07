from __future__ import unicode_literals

from setuptools import find_packages, setup


setup(
    name='indico-plugin-outlook',
    version='1.0',
    url='https://github.com/indico/indico-plugins-cern',
    license='MIT',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        'indico>=2.0a1'
    ],
    entry_points={
        'indico.plugins': {'outlook = indico_outlook.plugin:OutlookPlugin'},
    },
    classifiers=[
        'Environment :: Plugins',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
    ],
)
