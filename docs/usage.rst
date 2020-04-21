========
Usage
========

The ``jobrunner`` package is a Python API providing an abstraction layer to run jobs
on HPC clusters using Grid Engine, SLURM, Torque, or on the local computer.

When using ``jobrunner``, you do not need to execute ``qsub`` explicitly, the ``jobrunner``
package automatically builds and executes the correct ``qsub`` command for you.

To submit a job for execution on Grid Engine::

  from jobrunner import JobRunner
  runner = JobRunner("grid")  # This also works with "slurm" or "torque"
  command_line = "echo Hello World"
  job_id = runner.run(command_line, "JobName", "logfile.log")

To run a job locally on your computer, just change "grid" to "local". Everything else stays the same::

  from jobrunner import JobRunner
  runner = JobRunner("local")
  command_line = "echo Hello World"
  job_id = runner.run(command_line, "JobName", "logfile.log")

For an array-job, first create a file with array job parameters, one line per task::

  $ echo A B C > arrayfile
  $ echo 1 2 3 >> arrayfile


To submit an array-job for execution on Grid Engine::

  from jobrunner import JobRunner
  runner = JobRunner("grid")  # This also works locally, just change "grid" to "local"
  command_line = "echo Hello {1}{2}{3}"
  job_id = runner.run_array(command_line, "JobName", "logfile.log", "arrayfile")


Array job parameter substitution
--------------------------------

As you can see from the examples above, ``jobrunner`` has a very simple language for extracting parameters
from a file and substituting the parameters into a command line.

Parameters in the array job parameter file are whitespace-separated.  The parameters can have any meaning
you want -- numbers, strings, file names, directory names, etc.

The substitution language is just a number inside curly braces.

``{1}`` is the first parameter found in the array job parameter file.

``{2}`` is the second parameter found in the array job parameter file.

``{3}`` is the third parameter found in the array job parameter file.

...

``{9}`` is the 9th parameter found in the array job parameter file.

Currently, array jobs running locally have a limit of 9 parameters.  Array jobs running on the HPC have no limit
to the number of parameters per line in the array job parameter file.


jobrunner.jobrunner module
--------------------------

.. automodule:: jobrunner.jobrunner
    :members:
    :undoc-members:
    :show-inheritance:
    :noindex:

