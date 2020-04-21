===============================
jobrunner
===============================


.. Image showing the PyPI version badge - links to PyPI
.. image:: https://img.shields.io/pypi/v/jobrunner.svg
        :target: https://pypi.python.org/pypi/jobrunner

.. Image showing the Travis Continuous Integration test status, commented out for now
.. .. image:: https://img.shields.io/travis/CFSAN-Biostatistics/jobrunner.svg
..        :target: https://travis-ci.org/CFSAN-Biostatistics/jobrunner



An abstraction layer to run jobs on HPC clusters using Grid Engine, SLURM, Torque, or locally.

The jobrunner package was developed by the United States Food
and Drug Administration, Center for Food Safety and Applied Nutrition.

* Free software
* Documentation: https://jobrunner.readthedocs.io
* Source Code: https://github.com/CFSAN-Biostatistics/jobrunner
* PyPI Distribution: https://pypi.python.org/pypi/jobrunner


Features
--------

* Python API for job submission
* Consistent interface to run jobs on Grid Engine, SLURM, Torque, or locally
* Dependencies between jobs
* Array jobs and normal non-array jobs
* Array job parameter substitution
* Array job slot-dependency
* Limit the CPU resources consumed by array jobs
* Separate log files for each array job task


Citing jobrunner
--------------------------------------

To cite jobrunner, please reference the jobrunner GitHub repository:

    https://github.com/CFSAN-Biostatistics/jobrunner


License
-------

See the LICENSE file included in the jobrunner distribution.

