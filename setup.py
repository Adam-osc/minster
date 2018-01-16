# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))
exec(open('minFQ/version.py').read())

setup(
    name='minFQ',
    version=__version__,
    description='Command line interface for uploading fastq files and monitoring minKNOW in minotour.',
    long_description=open(path.join(here, "README.rst")).read(),
    url='https://github.com/LooseLab/mintourcli',
    author='Matt Loose',
    author_email='matt.loose@nottingham.ac.uk',
    license='MIT',
    classifiers=[
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='nanopore quality control analysis',
    packages=find_packages(),
    python_requires='>=3',
    setup_requires=['numpy'],
    install_requires=['tqdm',
                      'python-dateutil',
                      'requests',
                      'BioPython',
                      'numpy',
                      'watchdog',
                      'ws4py',
                      'configargparse'
                      ],
    package_data={'minFQ': []},
    package_dir={'minFQ': 'minFQ'},
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'minFQ=minFQ.minFQ:main',
        ],
    },
)
