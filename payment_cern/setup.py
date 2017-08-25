from __future__ import unicode_literals

from setuptools import setup, find_packages


setup(
    name='indico_payment_cern',
    version='0.4',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        'indico>=1.9.10'
    ],
    entry_points={'indico.plugins': {'payment_cern = indico_payment_cern.plugin:CERNPaymentPlugin'},
                  'indico.zodb_importers': {'payment_cern = indico_payment_cern.zodbimport:CERNPaymentImporter'}}
)
