from setuptools import setup, find_packages

with open('README.md', 'r') as f:
    long_description = f.read()

with open('requirements.txt', 'r') as f:
    install_requires = f.read().splitlines()

setup(
    name='docucompareapi',
    version='0.1.0',
    description='A FastAPI-based document comparison tool supporting Excel, PDFs, and Image files.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='',
    author='Prashant Pokhriyal',
    author_email='',
    license='MIT',
    packages=find_packages(where='app'),
    package_dir={'': 'app'},
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'docucompareapi=main:main',
        ],
    },
    platforms=["linux", "macos", "windows"],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.12',
    ],
    include_package_data=True,
    package_data={
        '': ['licenses/*', 'app/v1/static/*', 'app/log/*', 'config/*'],
    },
)