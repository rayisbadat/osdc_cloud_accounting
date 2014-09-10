from distutils.core import setup
setup(name='repquota',
    version='0.1',
    description = "Query and export quota stats via xinetd service",
    author = "Raymond Powell",
    author_email='rpowell1@uchicago.edu',
    classifiers = [
        "License :: OSI Approved :: Apache License v2",
        "Intended Audience :: Developers",
    ],
    url = "",
    py_modules=['repquota'],
    requires=[],
)
