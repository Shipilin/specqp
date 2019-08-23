from setuptools import setup, find_packages

setup(name='SpecQP',
      version='0.1',
      description='Quick plotting and correcting of spectroscopic data',
      url='https://github.com/Shipilin/specqp.git',
      author='Mikhail Shipilin',
      author_email='mikhail.shipilin@gmail.com',
      license='MIT',
      packages=find_packages(),
      include_package_data=True,
      unit_test='pytest',
      install_requires=['numpy', 'scipy', 'pandas', 'matplotlib'],
      classifiers=["Programming Language :: Python :: 3",
                   "License :: OSI Approved :: MIT License",
                   "Operating System :: Mac OSX"]
      )
