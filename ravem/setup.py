from setuptools import setup, find_packages

setup(
    name='indico_ravem',
    version='0.1',
    url='https://gitlab.cern.ch/indico/indico-plugins-cern',
    author='Indico Team',
    author_email='indico-team@cern.ch',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=[
        'indico>=1.9.1'
    ],
    test_requires=[
        'responses>=0.3.0'
    ],
    entry_points={'indico.plugins': {'ravem = indico_ravem.plugin:RavemPlugin'},
                  'indico.zodb_importers': {'ravem = indico_ravem.zodbimport:RavemImporter'}}
)
