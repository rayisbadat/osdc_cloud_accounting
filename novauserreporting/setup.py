from distutils.core import setup
setup(name='novauserreporting',
    version='0.1',
    description = "Query and export cloud stats",
    author = "Raymond Powell",
    author_email='rpowell1@uchicago.edu',
    classifiers = [
        "License :: OSI Approved :: Apache License v2",
        "Intended Audience :: Developers",
    ],
    url = "",
    py_modules=['novauserreporting'],
    requires=['pollgluster (>= 0.1)'],
)
