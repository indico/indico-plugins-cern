from setuptools import setup, find_packages


setup(
    name='indico_outlook',
    version='0.2',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'indico>=1.9.2'
    ],
    entry_points={'indico.plugins': {'outlook = indico_outlook.plugin:OutlookPlugin'},
                  'indico.zodb_importers': {'outlook = indico_outlook.zodbimport:OutlookImporter'}}
)
