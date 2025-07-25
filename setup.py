from setuptools import setup, find_packages

setup(name='flashcard',
      version='0.1.0',
      description='my flashcards',
      author='gront',
      packages=find_packages(),
      install_requires=[
          'beautifulsoup4',
          'requests',
          'networkx',
          'matplotlib',
          'numpy',
      ],
     )