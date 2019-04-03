from setuptools import setup, find_packages

setup(name='specqp',
      version='0.1',
      description='Quick plotting and correcting spectroscopic data',
      url='https://github.com/Shipilin/specqp.git',
      author='Mikhail Shipilin',
      author_email='mikhail.shipilin@gmail.com',
      license='MIT',
      packages=find_packages(),
      include_package_data=True,
      unit_test='unittest',
      install_requires=['numpy', 'scipy', 'pandas', 'matplotlib']
      )
