from distutils.core import setup
setup(name='pollgluster',
    version='0.1',
    description = "Query and export gluster stats",
    author = "Raymond Powell",
    author_email='rpowell1@uchicago.edu',
    classifiers = [
        "License :: OSI Approved :: Apache License v2",
        "Intended Audience :: Developers",
    ],
    url = "",
    py_modules=['pollgluster'],
    requires=['unitconversion (>= 0.1)'],
)
