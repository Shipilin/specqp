from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
      name='specqp',
      version='1.1.5',
      description='Quick plotting, correcting and fitting of spectroscopic data',
      long_description=long_description,
      long_description_content_type="text/markdown",
      url='https://github.com/Shipilin/specqp.git',
      author='Mikhail Shipilin',
      author_email='mikhail.shipilin@gmail.com',
      license='MIT',
      packages=find_packages(),
      include_package_data=True,
      unit_test='pytest',
      install_requires=['numpy', 'scipy', 'pandas', 'matplotlib', 'lmfit'],
      classifiers=["Programming Language :: Python :: 3",
                   "License :: OSI Approved :: MIT License",
                   "Intended Audience :: Science/Research",
                   "Natural Language :: English",
                   "Operating System :: MacOS :: MacOS X",
                   "Operating System :: Microsoft :: Windows",
                   "Environment :: MacOS X",
                   "Development Status :: 5 - Production/Stable"]
      )
