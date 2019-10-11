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


def test_noisy_run(tmpdir, capfd):
    """Verify tee output to stdout when not in quiet mode, and logfile captures all.
    """
    log_file_path = tmpdir.join("logfile.log")

    runner = JobRunner("local")
    runner.run("(echo text to stdout; echo text to stderr 1>&2)", "JobName", str(log_file_path), quiet=False)
    captured = capfd.readouterr()

    assert(tmpdir.join("logfile.log").read() == 'text to stdout\ntext to stderr\n')
    assert("text to stdout" in captured.out)
    assert("text to stderr" in captured.out)
    assert(len(captured.err) == 0)


def test_quiet_run(tmpdir, capfd):
    """Verify NO tee output to stdout when not in quiet mode, and logfile captures all.
    """
    log_file_path = tmpdir.join("logfile.log")

    runner = JobRunner("local")
    runner.run("(echo text to stdout; echo text to stderr 1>&2)", "JobName", str(log_file_path), quiet=True)
    captured = capfd.readouterr()

    assert(tmpdir.join("logfile.log").read() == 'text to stdout\ntext to stderr\n')
    assert(len(captured.out) == 0)
    assert(len(captured.err) == 0)


def test_noisy_array_run(tmpdir, capfd):
    """Verify tee output to stdout when not in quiet mode, and logfile captures all.
    """
    array_file_path = tmpdir.join("array_file")
    array_file_path.write("text\n")
    log_file_path = tmpdir.join("logfile.log")

    runner = JobRunner("local")
    runner.run_array("(echo {1} to stdout; echo {1} to stderr 1>&2)", "JobName", str(log_file_path), str(array_file_path), quiet=False)
    captured = capfd.readouterr()

    assert(tmpdir.join("logfile.log-1").read() == 'text to stdout\ntext to stderr\n')
    assert("text to stdout" in captured.out)
    assert("text to stderr" in captured.out)
    assert(len(captured.err) == 0)


def test_quiet_array_run(tmpdir, capfd):
    """Verify NO tee output to stdout when not in quiet mode, and logfile captures all.
    """
    array_file_path = tmpdir.join("array_file")
    array_file_path.write("text\n")
    log_file_path = tmpdir.join("logfile.log")

    runner = JobRunner("local")
    runner.run_array("(echo {1} to stdout; echo {1} to stderr 1>&2)", "JobName", str(log_file_path), str(array_file_path), quiet=True)
    captured = capfd.readouterr()

    assert(tmpdir.join("logfile.log-1").read() == 'text to stdout\ntext to stderr\n')
    assert(len(captured.out) == 0)
    assert(len(captured.err) == 0)
