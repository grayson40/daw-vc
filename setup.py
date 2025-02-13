from setuptools import setup

setup(
    name='daw',
    version='0.1',
    packages=['src.fl_studio', 'src.fl_studio.parser', 'src.fl_studio.diff'],
    install_requires=[
        'click',
        'pyflp'
    ],
    entry_points={
        'console_scripts': [
            'daw=src.cli.cli:cli',
        ],
    },
)