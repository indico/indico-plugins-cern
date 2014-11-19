from setuptools import setup


setup(
    name='indico_foundationsync',
    version='1.0',
    py_modules=('indico_foundationsync',),
    zip_safe=False,
    platforms='any',
    install_requires=[
        'indico>=1.9.1',
        'cx_Oracle'
    ],
    entry_points={'indico.plugins': {'foundationsync = indico_foundationsync:FoundationSyncPlugin'}}
)
