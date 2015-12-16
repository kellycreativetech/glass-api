from setuptools import setup, find_packages
setup(
    name = "glass",
    version = "0.1.0",
    packages = find_packages(),
    scripts = ['glass.py'],

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    install_requires = ['requests==2.8.1', 'click==6.2', 'pathspec==0.3.4', 'watchdog==0.8.3'],

    package_data = {},
    entry_points={
          'console_scripts': [
              'glass = glass:cli'
          ]
      },

    # metadata for upload to PyPI
    author = "Issac Kelly",
    author_email = "issac@servee.com",
    description = "Glass CLI",
)