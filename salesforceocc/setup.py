from distutils.core import setup
setup(name='salesforceocc',
    version='0.1',
    description = "Allows OCC scripts/apps to interact with SalesForce",
    author = "Raymond Powell",
    author_email='rpowell1@uchicago.edu',
    classifiers = [
        "License :: OSI Approved :: Apache License v2",
        "Intended Audience :: Developers",
    ],
    url = "",
    py_modules=['salesforceocc'],
    requires=['Beatbox (>= 0.92)'],

)
