from __future__ import unicode_literals

from setuptools import find_packages, setup


setup(
    name='indico-plugin-payment-cern',
    version='1.0',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=[
        'indico>=2.0a1'
    ],
    entry_points={
        'indico.plugins': {'payment_cern = indico_payment_cern.plugin:CERNPaymentPlugin'},
    }
)
