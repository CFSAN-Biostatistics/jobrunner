# -*- coding: utf-8 -*-

"""
test_jobrunner
----------------------------------

Tests for `jobrunner` module.
"""

from jobrunner import JobRunner


def test_arrayjob(tmpdir):
    """Verify array jobs have multiple processes, separate log files for each task, and support parameter substitution..
    """
    array_file_path = tmpdir.join("array_file")
    array_file_path.write("World 1\nWorld 2\nWorld 3\n")
    log_file_path = tmpdir.join("logfile.log")

    runner = JobRunner("local")
    runner.run_array("echo Hello {1} {2}", "JobName", str(log_file_path), str(array_file_path))

    assert(tmpdir.join("logfile.log-1").read() == "Hello World 1\n")
    assert(tmpdir.join("logfile.log-2").read() == "Hello World 2\n")
    assert(tmpdir.join("logfile.log-3").read() == "Hello World 3\n")
