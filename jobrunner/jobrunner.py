"""
This module provides an abstraction layer to run jobs on high performance computers
using torque, grid, or locally with xargs.
"""

from __future__ import print_function
from __future__ import absolute_import

import os
import psutil
import subprocess
import sys


# Determine how to decode bytes
std_encoding = sys.stdout.encoding
if std_encoding is None:
    std_encoding = sys.stdin.encoding
if std_encoding is None:
    std_encoding = "utf-8"


class JobRunnerException(Exception):
    """Raised for fatal JobRunner errors"""


class JobRunner(object):
    def __init__(self, hpc_type, strip_job_array_suffix=True, qsub_extra_params=None, exception_handler=None, verbose=False):
        """Initialize an hpc job runner object.

        Parameters
        ----------
        hpc_type : str
            Type of job runner.  Possible values are "grid", "slurm", "torque", and "local".
        strip_job_array_suffix : bool, optional defaults to True
            When true, the dot and array suffix in the job id is removed before returning the job id.
        qsub_extra_params : str, optional defaults to None
            Extra command line options passed to qsub or sbatch every time a job is submitted.
        exception_handler : function, optional defalts to None
            Function to be called in local mode only when an exception occurs while attempting to run an
            external process. The function will be called with the arguments (exc_type, exc_value, exc_traceback).
        verbose : bool, optional defaults to False
            When true, the job command lines are logged.

        Examples
        --------
        >>> runner = JobRunner("foobar")
        Traceback (most recent call last):
        ValueError: hpc_type must be one of: "grid", "slurm", "torque", "local"
        """
        hpc_type = hpc_type.lower()
        if hpc_type not in ["grid", "slurm", "torque", "local"]:
            raise ValueError('hpc_type must be one of: "grid", "slurm", "torque", "local"')

        self.hpc_type = hpc_type
        self.strip_job_array_suffix = strip_job_array_suffix
        self.qsub_extra_params = qsub_extra_params
        self.exception_handler = exception_handler
        self.verbose = verbose

        if hpc_type == 'grid':
            self.subtask_env_var_name = "SGE_TASK_ID"
        elif hpc_type == 'slurm':
            self.subtask_env_var_name = "SLURM_ARRAY_TASK_ID"
        elif hpc_type == 'torque':
            self.subtask_env_var_name = "PBS_ARRAYID"

    def _make_qsub_command(self, job_name, log_file, wait_for=[], wait_for_array=[], slot_dependency=False, threads=1, parallel_environment=None, num_tasks=None, max_processes=None, exclusive=False, wall_clock_limit=None):
        """Create the command line to run a job on a computing cluster.

        Parameters
        ----------
        job_name : str
            Job name that will appear in the job scheduler queue.
        log_file : str
            Path to the combined stdout / stderr log file.
        wait_for : str or list of str, optional defaults to empty list
            Single job id or list of jobs ids to wait for before beginning execution.
        wait_for_array : str or list of str, optional defaults to empty list
            Single array job id or list of array jobs ids to wait for before beginning execution.
        slot_dependency : bool, optional defaults to False
            Enforced for grid engine and slurm only.  Ignored for all other schedulers.
            If true, the sub-tasks of the array job being submitted will be dependent on the
            completion of the corresponding sub-tasks of the jobs in the wait_for_array.  Has
            no effect on the dependencies of non-array jobs.
        threads : int, optional defaults to 1
            Number of CPU threads consumed by the job.
        parallel_environment : str, optional defaults to None
            Name of the grid engine parallel execution environment.  This must be specified when
            consuming more than one thread on grid engine.  Ununsed for any other job scheduler.
        num_tasks : int, optional defaults to None
            When specified, the job becomes an array job with num_tasks sub-tasks.
        max_processes : int, optional defaults to None
            If not None, it sets the maximium number of concurrent processes for an array job.
        exclusive : bool, optional, defaults to False
            Requests exclusive access to compute nodes to prevent other jobs from sharing the node resources.
            Enforced only on SLURM, silently ignored for all other schedulers.
        wall_clock_limit : str, optional, defaults to None
            Maximum run-time; string of the form HH:MM:SS.


        Returns
        -------
        command_line : str
            Job submission command line for Grid, SLURM, or torque.

        Examples
        --------
        >>> runner = JobRunner("local")
        >>> runner._make_qsub_command("JobName", "log")
        Traceback (most recent call last):
        ValueError: _make_qsub_command() does not support hpc type local

        # grid
        # =======
        >>> runner = JobRunner("grid", qsub_extra_params="-q service.q")
        >>> runner._make_qsub_command("JobName", "log", "777", "888", threads=8, parallel_environment="mpi")
        'qsub -terse -V -j y -cwd -N JobName -o log -hold_jid 777,888 -pe mpi 8 -q service.q'

        >>> runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], threads=8, parallel_environment="mpi", wall_clock_limit="00:00:40")
        'qsub -terse -V -j y -cwd -N JobName -o log -hold_jid 666,777,888,999 -pe mpi 8 -l h_rt=00:00:40 -q service.q'

        >>> runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], slot_dependency=True, threads=8, parallel_environment="mpi")
        'qsub -terse -V -j y -cwd -N JobName -o log -hold_jid 666,777 -hold_jid_ad 888,999 -pe mpi 8 -q service.q'

        # array job
        >>> runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], slot_dependency=True, threads=8, parallel_environment="mpi", num_tasks=99, max_processes=2, wall_clock_limit="00:00:40")
        'qsub -terse -t 1-99 -V -j y -cwd -N JobName -o log -hold_jid 666,777 -hold_jid_ad 888,999 -tc 2 -pe mpi 8 -l h_rt=00:00:40 -q service.q'


        # slurm
        # =======
        >>> runner = JobRunner("slurm", qsub_extra_params="-p short.q")
        >>> runner._make_qsub_command("JobName", "log", "777", "888", threads=8)
        'sbatch --parsable --export=ALL --job-name=JobName -o log --dependency=afterok:777:888 --cpus-per-task=8 -p short.q'

        >>> runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], threads=8, wall_clock_limit="00:00:40")
        'sbatch --parsable --export=ALL --job-name=JobName -o log --dependency=afterok:666:777:888:999 --cpus-per-task=8 --time 00:00:40 -p short.q'

        # array job
        >>> runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], slot_dependency=False, threads=8, num_tasks=44, max_processes=2, wall_clock_limit="00:00:40")
        'sbatch --parsable --array=1-44%2 --export=ALL --job-name=JobName -o log --dependency=afterok:666:777:888:999 --cpus-per-task=8 --time 00:00:40 -p short.q'

        >>> runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], slot_dependency=True, threads=8, num_tasks=44, max_processes=2)
        'sbatch --parsable --array=1-44%2 --export=ALL --job-name=JobName -o log --dependency=afterok:666:777,aftercorr:888:999 --cpus-per-task=8 -p short.q'

        # exclusive node access
        >>> runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], slot_dependency=False, threads=8, num_tasks=44, max_processes=2, exclusive=True)
        'sbatch --parsable --exclusive --array=1-44%2 --export=ALL --job-name=JobName -o log --dependency=afterok:666:777:888:999 --cpus-per-task=8 -p short.q'

        # torque
        # =======
        >>> runner = JobRunner("torque", qsub_extra_params="-q short.q")
        >>> cmd = runner._make_qsub_command("JobName", "log", "777", "888", threads=8)
        >>> cmd == "qsub -V -j oe -d %s -N JobName -o log -W depend=afterok:777,afterokarray:888 -l nodes=1:ppn=8 -q short.q" % os.getcwd()
        True

        >>> cmd = runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], threads=8, wall_clock_limit="00:00:40")
        >>> cmd == "qsub -V -j oe -d %s -N JobName -o log -W depend=afterok:666:777,afterokarray:888:999 -l nodes=1:ppn=8 -l walltime=00:00:40 -q short.q" % os.getcwd()
        True

        # array job
        >>> cmd = runner._make_qsub_command("JobName", "log", ["666", "777"], ["888", "999"], slot_dependency=True, threads=8, num_tasks=44, max_processes=2)
        >>> cmd == "qsub -t 1-44%%2 -V -j oe -d %s -N JobName -o log -W depend=afterok:666:777,afterokarray:888:999 -l nodes=1:ppn=8 -q short.q" % os.getcwd()
        True
        """
        if self.hpc_type not in ["grid", "slurm", "torque"]:
            raise ValueError("_make_qsub_command() does not support hpc type %s" % self.hpc_type)

        if self.hpc_type == "grid":
            array_option = " -t 1-" + str(num_tasks) if num_tasks else ""
            qsub_command_line = "qsub -terse" + array_option + " -V -j y -cwd -N " + job_name + " -o " + log_file

            if isinstance(wait_for, str):
                wait_for = [wait_for]
            if isinstance(wait_for_array, str):
                wait_for_array = [wait_for_array]
            if not slot_dependency:
                wait_for.extend(wait_for_array)  # combine lists
            if len(wait_for) > 0:
                qsub_command_line += " -hold_jid " + ','.join(wait_for)
            if slot_dependency and len(wait_for_array) > 0:
                qsub_command_line += " -hold_jid_ad " + ','.join(wait_for_array)

            if max_processes:
                qsub_command_line += " -tc " + str(max_processes)
            if threads > 1:
                if not parallel_environment:
                    raise ValueError("You must use a parallel environment when consuming more than one thread on grid engine")
                qsub_command_line += " -pe " + parallel_environment + ' ' + str(threads)

            if wall_clock_limit:
                qsub_command_line += " -l h_rt=" + wall_clock_limit

            if self.qsub_extra_params:
                qsub_command_line += ' ' + self.qsub_extra_params
            return qsub_command_line

        if self.hpc_type == "slurm":
            exclusive_option = " --exclusive" if exclusive else ""
            max_processes_option = "%%%i" % max_processes if max_processes else ""
            array_option = " --array=1-" + str(num_tasks) + max_processes_option if num_tasks else ""
            qsub_command_line = "sbatch --parsable" + exclusive_option + array_option + " --export=ALL --job-name=" + job_name + " -o " + log_file

            if isinstance(wait_for, str):
                wait_for = [wait_for]
            if isinstance(wait_for_array, str):
                wait_for_array = [wait_for_array]
            if not slot_dependency:
                wait_for.extend(wait_for_array)  # combine lists
                wait_for_array = []
            dependencies = []
            if len(wait_for) > 0:
                dependencies.append("afterok:" + ':'.join(wait_for))
            if len(wait_for_array) > 0 and slot_dependency:
                dependencies.append("aftercorr:" + ':'.join(wait_for_array))
            if len(dependencies) > 0:
                qsub_command_line += " --dependency=" + ','.join(dependencies)

            if threads > 1:
                qsub_command_line += " --cpus-per-task=" + str(threads)

            if wall_clock_limit:
                qsub_command_line += " --time " + wall_clock_limit

            if self.qsub_extra_params:
                qsub_command_line += ' ' + self.qsub_extra_params
            return qsub_command_line

        if self.hpc_type == "torque":
            max_processes_option = "%%%i" % max_processes if max_processes else ""
            array_option = " -t 1-" + str(num_tasks) + max_processes_option if num_tasks else ""
            qsub_command_line = "qsub" + array_option + " -V -j oe -d " + os.getcwd() + " -N " + job_name + " -o " + log_file

            if isinstance(wait_for, str):
                wait_for = [wait_for]
            if isinstance(wait_for_array, str):
                wait_for_array = [wait_for_array]
            dependencies = []
            if len(wait_for) > 0:
                dependencies.append("afterok:" + ':'.join(wait_for))
            if len(wait_for_array) > 0:
                dependencies.append("afterokarray:" + ':'.join(wait_for_array))
            if len(dependencies) > 0:
                qsub_command_line += " -W depend=" + ','.join(dependencies)

            if threads > 1:
                qsub_command_line += " -l nodes=1:ppn=" + str(threads)

            if wall_clock_limit:
                qsub_command_line += " -l walltime=" + wall_clock_limit

            if self.qsub_extra_params:
                qsub_command_line += ' ' + self.qsub_extra_params
            return qsub_command_line

    def run(self, command_line, job_name, log_file, wait_for=[], wait_for_array=[], threads=1, parallel_environment=None, exclusive=False, wall_clock_limit=None, quiet=False):
        """Run a non-array job.  Stderr is redirected (joined) to stdout.

        Parameters
        ----------
        command_line : str
            Command with all arguments to be executed.
        job_name : str
            Job name that will appear in the job scheduler queue.
        log_file : str
            Path to the combined stdout / stderr log file.
        wait_for : str or list of str, optional defaults to empty list
            Single job id or list of jobs ids to wait for before beginning execution.
            Ignored when running locally.
        wait_for_array : str or list of str, optional defaults to empty list
            Single array job id or list of array jobs ids to wait for before beginning execution.
            Ignored when running locally.
        threads : int, optional defaults to 1
            Number of CPU threads consumed by the job, unused when running locally.
        parallel_environment : str, optional defaults to None
            Name of the grid engine parallel execution environment.  This must be specified when
            consuming more than one thread on grid engine.  Ununsed for any other job scheduler.
        exclusive : bool, optional, defaults to False
            Requests exclusive access to compute nodes to prevent other jobs from sharing the node resources.
            Enforced only on SLURM, silently ignored for all other schedulers.
        wall_clock_limit : str, optional, defaults to None
            Maximum run-time; string of the form HH:MM:SS.
            Ignored when running locally.
        quiet : bool, optional, defaults to False
            Controls whether the job stderr and stdout are written to stdout in addition to the log file.
            By default, the job stderr and stdout are written to both stdout and the log file.
            When True, the job stderr and stdout are written to the log file only.

        Returns
        -------
        job_id : str
            Grid or torque job id.  Returns '0' in local mode.

        Raises
        ------
        CalledProcessError

        In local mode, non-zero exit codes will raise CalledProcessError and the exception will be routed to the exception handler installed during JobRunner initialization, if any.  If no exception handler was specified, the exception is re-raised.

        Examples
        --------
        >>> # Normal case - verify job id is '0', stdout and stderr written to log file
        >>> from tempfile import NamedTemporaryFile
        >>> fout = NamedTemporaryFile(delete=False, mode='w'); fout.close()
        >>> runner = JobRunner("local")
        >>> # Parenthesis are needed when the command line contains multiple commands separated by semicolon
        >>> job_id = runner.run("(echo text to stdout; echo text to stderr 1>&2)", "JobName", fout.name)
        >>> type(job_id) == type("this is a string")
        True
        >>> job_id
        '0'
        >>> f = open(fout.name); out = f.read(); f.close(); os.unlink(fout.name)
        >>> print(out.strip())
        text to stdout
        text to stderr

        >>> # Error case, external program returns non-zero.
        >>> # Need to ignore exception details to work with both python2 and python3.
        >>> job_id = runner.run("exit 100", "JobName", "") # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        CalledProcessError: Command 'set -o pipefail; exit 100 2>&1 | tee ' returned non-zero exit status 100
        """
        if self.hpc_type == "local":
            redirection = " > " + log_file + " 2>&1 " if quiet else " 2>&1 | tee " + log_file
            command_line = "set -o pipefail; " + command_line + redirection
            if self.verbose:
                print(command_line)

            # flush stdout to keep the unbuffered stderr in chronological order with stdout
            sys.stdout.flush()

            # Run command. Wait for command to complete. If the return code was zero then return, otherwise raise CalledProcessError
            try:
                subprocess.check_call(command_line, shell=True, executable="bash")
            except subprocess.CalledProcessError:
                if self.exception_handler:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    self.exception_handler(exc_type, exc_value, exc_traceback)
                else:
                    raise
            return '0'

        else:  # grid, slurm, or torque
            qsub_command_line = self._make_qsub_command(job_name, log_file, wait_for, wait_for_array, threads=threads, parallel_environment=parallel_environment, exclusive=exclusive, wall_clock_limit=wall_clock_limit)

            # Run command and return its stdout output as a byte string.
            # If the return code was non-zero it raises a CalledProcessError.

            if self.hpc_type == "slurm":
                command_line = "'#!/bin/sh\\n'" + command_line

            shell_command_line = "echo -e " + command_line + " | " + qsub_command_line
            if self.verbose:
                print(shell_command_line)
            job_id = subprocess.check_output(shell_command_line, shell=True)
            if sys.version_info > (3,):
                job_id = job_id.decode(std_encoding)  # Python 3 stdout is bytes, not str
            job_id = job_id.strip()
            if self.verbose:
                print("Job id=" + job_id)
            return job_id

    def run_array(self, command_line, job_name, log_file, array_file, num_tasks=None, max_processes=None, wait_for=[], wait_for_array=[], slot_dependency=False, threads=1, parallel_environment=None, array_subshell=True, exclusive=False, wall_clock_limit=None, quiet=False):
        """Run an array of sub-tasks with the work of each task defined by a single line in the specified array_file.

        Parameters
        ----------
        command_line : str
            Command to be executed with parameter placeholders of the form {1}, {2}, {3} ...
        job_name : str
            Job name that will appear in the job scheduler queue.
        log_file : str
            Path to the combined stdout / stderr log file.  The sub-task number will be automatically appended.
        array_file : str
            Name of the file containing the arguments for each sub-task with one line
            per sub-task.  The arguments for each sub-task are found at the line number
            corresponding to the sub-task number.  The line is parsed and substituted
            into the command, replacing the parameter placeholders with the actual arguments.
        num_tasks : int, optional defaults to None
            Defines the number of subtasks in the job array.  If not specified, the array_file must exist
            and the number of tasks will be equal to the number of lines in the file.  Use this option
            when the array_file does not pre-exist and is created by a process that has not run yet.
        max_processes : int, optional defaults to None
            If None, the number of concurrent processes is limited to available CPU on an HPC
            and limited to the number of CPU cores when run locally.
            If not None, it sets the maximium number of concurrent processes for the array job.
            This works locally with xargs, and with grid and torque.
        wait_for : str or list of str, optional defaults to empty list
            Single job id or list of jobs ids to wait for before beginning execution.
            Ignored when running locally.
        wait_for_array : str or list of str, optional defaults to empty list
            Single array job id or list of array jobs ids to wait for before beginning execution.
            Ignored when running locally.
        slot_dependency : bool, optional defaults to False
            Ignored for all schedulers but grid engine.
            If true, the sub-tasks of the array job being submitted will be dependent on the
            completion of the corresponding sub-tasks of the jobs in the wait_for_array.  Has
            no effect on the dependencies of non-array jobs.
        threads : int, optional defaults to 1
            Number of CPU threads consumed by each sub-task of the job, unused when running locally.
        parallel_environment : str, optional defaults to None
            Name of the grid engine parallel execution environment.
            Ununsed for any other job scheduler.
        array_subshell : bool, optional defaults to True
            When true, HPC array job command lines are quoted and executed in a subshell.
            When running locally, this parameter is ignored -- commands are not quoted and always run in a subshell.
        exclusive : bool, optional, defaults to False
            Requests exclusive access to compute nodes to prevent other jobs from sharing the node resources.
            Enforced only on SLURM, silently ignored for all other schedulers.
        wall_clock_limit : str, optional, defaults to None
            Maximum run-time; string of the form HH:MM:SS.
            Ignored when running locally.
        quiet : bool, optional, defaults to False
            Controls whether the job stderr and stdout are written to stdout in addition to the log file.
            By default, the job stderr and stdout are written to both stdout and the log file.
            When True, the job stderr and stdout are written to the log file only.

        Returns
        -------
        job_id : str
            Grid or torque job id.  Returns '0' in local mode.

        Raises
        ------
        JobRunnerException

        If the array_file is missing or empty, and num_tasks is not specified, JobRunnerException is raised.

        In local mode, non-zero exit codes will raise CalledProcessError and the exception will be routed to the exception handler installed during JobRunner initialization, if any.  If no exception handler was specified, the exception is re-raised.
        """
        # Determine the number of array slots
        if not num_tasks:
            if not os.path.isfile(array_file):
                raise JobRunnerException("The file %s does not exist.\nCannot start array job %s." % (array_file, job_name))
            if os.path.getsize(array_file) == 0:
                raise JobRunnerException("The file %s is empty.\nCannot start array job %s." % (array_file, job_name))

            with open(array_file) as f:
                num_tasks = sum(1 for line in f)

        if self.hpc_type == "grid":
            log_file += "-\\$TASK_ID"
        elif self.hpc_type == "slurm":
            log_file += "-%a"

        if self.hpc_type == "local":
            # Change parameter placeholder into bash variables ready to feed to bash through xargs
            for param_num in range(1, 10):
                placeholder = '{' + str(param_num) + '}'
                command_line = command_line.replace(placeholder, '$' + str(param_num))

            # Use all CPU cores, if no limit requested
            if max_processes is None:
                max_processes = psutil.cpu_count()

            # Number the tasks with nl to get the task number into the log file suffix.
            # Allow up to 9 parameters per command.
            redirection = " > " + log_file + "-$0 2>&1'" if quiet else " 2>&1 | tee " + log_file + "-$0'"
            command_line = "head -n " + str(num_tasks) + " " + array_file + " | nl | xargs -P " + str(max_processes) + " -n 9 -L 1 bash -c + 'set -o pipefail; " + command_line + redirection
            if self.verbose:
                print(command_line)

            # flush stdout to keep the unbuffered stderr in chronological order with stdout
            sys.stdout.flush()

            # Run command. Wait for command to complete
            try:
                subprocess.check_call(command_line, shell=True, executable="bash")  # If the return code is non-zero it raises a CalledProcessError
            except subprocess.CalledProcessError:
                if self.exception_handler:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    self.exception_handler(exc_type, exc_value, exc_traceback)
                else:
                    raise
            return '0'

        else:  # grid, slurm, or torque
            qsub_command_line = self._make_qsub_command(job_name, log_file, wait_for, wait_for_array, slot_dependency, threads, parallel_environment, num_tasks, max_processes, exclusive=exclusive, wall_clock_limit=wall_clock_limit)

            if array_subshell:
                command_line = '"' + command_line + '"'
                compute_node_command = "qarrayrun --shell " + self.subtask_env_var_name + ' ' + array_file + ' ' + command_line
            else:
                compute_node_command = "qarrayrun " + self.subtask_env_var_name + ' ' + array_file + ' ' + command_line

            compute_node_command = "'" + compute_node_command + "'"

            if self.hpc_type == "slurm":
                compute_node_command = "'#!/bin/sh\\n'" + compute_node_command

            shell_command_line = "echo -e " + compute_node_command + " | " + qsub_command_line

            if self.verbose:
                print(shell_command_line)

            job_id = subprocess.check_output(shell_command_line, shell=True)  # If the return code is non-zero it raises a CalledProcessError
            if sys.version_info > (3,):
                job_id = job_id.decode(std_encoding)  # Python 3 stdout is bytes, not str
            job_id = job_id.strip()
            if self.strip_job_array_suffix:
                dot_idx = job_id.find('.')
                if dot_idx > 0:
                    job_id = job_id[0: dot_idx]
            if self.verbose:
                print("Job id=" + job_id)
            return job_id
