import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="DyphanBot",
    author="Buzzbyte",
    description="An Extensible Discord Bot",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/buzzbyte/DyphanBot",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: POSIX",
        "Development Status :: 3 - Alpha"
    ],
    python_requires='>=3.6',
)