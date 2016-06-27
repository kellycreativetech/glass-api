from setuptools import setup, find_packages
import re

with open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()
with open('HISTORY.rst', 'r', 'utf-8') as f:
    history = f.read()

with open('glass.py', 'r') as fd:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        fd.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError('Cannot find version information')

setup(
    name="glass-cli",
    version=version,
    packages=find_packages(),
    scripts=['glass.py'],
    package_data={},
    entry_points={
          'console_scripts': [
              'glass = glass:cli'
          ]
    },
    classifiers=(
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Environment :: Console',
        'Topic :: Internet',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
    ),
    # metadata for upload to PyPI
    license='Apache 2.0',
    author="Servee LLC - Issac Kelly",
    author_email="issac@servee.com",
    description="Glass CLI",
    install_requres=[
        'click==6.6',
        'requests==2.10.0',
        'pathspec==0.3.4',
        'watchdog==0.8.3',
        'Django==1.9.7',
        'opbeat==3.3.2',
    ],
    long_description=readme + '\n\n' + history,
)
