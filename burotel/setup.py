from __future__ import unicode_literals

from setuptools import setup


setup(
    name='indico-plugin-burotel',
    version='1.0',
    url='https://github.com/indico/indico-plugins-cern',
    license='MIT',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    py_modules=('indico_burotel',),
    zip_safe=False,
    install_requires=[
        'indico>=2.0a1'
    ],
    entry_points={
        'indico.plugins': {'burotel = indico_burotel:BurotelPlugin'}
    },
    classifiers=[
        'Environment :: Plugins',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
    ],
)
