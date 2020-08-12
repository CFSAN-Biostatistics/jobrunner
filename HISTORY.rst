.. :changelog:

History
=======

1.3.1 (2020-08-12)
---------------------
* Allow array tasks in local mode to process only a portion of the lines in the array file
  by setting ``num_tasks`` to a value less than the number of lines in the array file.

1.3.0 (2020-04-12)
---------------------
* Add support for the SLURM job scheduler.
* Add capability to request exclusive access to compute nodes when running on SLURM.

1.2.0 (2019-10-11)
---------------------
* Add the capability to run in quiet mode when running locally on a workstation
  so the job stdout and stderr are written to log files only.

1.1.0 (2019-06-07)
---------------------
* HPC array job command lines are quoted and executed in a subshell by default with better support for complex command lines.

1.0.0 (2018-12-03)
---------------------

* First public release.
