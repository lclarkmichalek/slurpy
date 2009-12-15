import os
from setuptools import setup, find_packages
import sys
 
version = '3.0.0'
 
setup(name='slurpy',
      version=version,
      description="An Arch User Repository (AUR) search/download/update helper",
      author='Randy Morris',
      author_email='randy.morris@rsontech.net',
      url='http://rsontech.net/projects/slurpy',
      packages=find_packages(),
      entry_points="""
# -*- Entry points: -*-
[console_scripts]
slurpy=slurpy.slurpy:main
""",
      )
