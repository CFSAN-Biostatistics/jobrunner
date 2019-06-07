# -*- coding: utf-8 -*-


from __future__ import absolute_import

# Expose JobRunner at the package level so apps can do this: from jobrunner import JobRunner
from jobrunner.jobrunner import JobRunner, JobRunnerException  # noqa: F401

__author__ = 'Steve Davis'
__email__ = 'steven.davis@fda.hhs.gov'
__version__ = '1.1.0'
