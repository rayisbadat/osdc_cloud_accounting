#   Copyright 2014 Center for Data Intensive Sciences (CDIS)
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

from distutils.core import setup
setup(name='repswiftquota',
    version='0.1',
    description = "Query and save swift du stats for later retrival (cant use cielometer with ceph)",
    author = "Raymond Powell",
    author_email='rpowell1@uchicago.edu',
    classifiers = [
        "License :: OSI Approved :: Apache License v2",
        "Intended Audience :: Developers",
    ],
    url = "",
    py_modules=['repswiftdu'],
    requires=[],
)
