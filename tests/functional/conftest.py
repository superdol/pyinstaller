#-----------------------------------------------------------------------------
# Copyright (c) 2005-2015, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License with exception
# for distributing bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------


import os
import pytest

from PyInstaller import compat, configure
from PyInstaller import main as pyi_main


# Directory with Python scripts for functional tests. E.g. main scripts, etc.
_SCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'support')


# TODO pyinst config dir in tmp.
# TODO move to file conftest.py.
class AppBuilder(object):

    def __init__(self, tmpdir):
        self._tmpdir = tmpdir
        self._specdir = self._tmpdir
        self._distdir = os.path.join(self._tmpdir, 'dist')
        self._builddir = os.path.join(self._tmpdir, 'build')

    def test_script(self, script):
        """
        Main method to wrap all phases of testing a Python script.

        :param script: Name of script to create executable from.
        """
        self.script_name = os.path.basename(script)
        self.script = os.path.join(_SCRIPT_DIR, script)
        assert os.path.exists(self.script), 'Script %s not found.' % script
        self.toc_files = None

        assert self._test_building(), 'Building of %s failed.' % script
        retcode = self._test_execution()
        assert retcode == 0, 'Running exe of %s failed with return-code %s.' % (script, retcode)
        # TODO implement examining toc files for multipackage tests.
        assert self._test_created_files(), 'Matching .toc of %s failed.' % script

    def _test_execution(self):
        """
        Run created executable to make sure it works.

        :return: Exit code of the executable.
        """
        return 0

    def _test_created_files(self):
        """
        Examine files that were created by PyInstaller.

        :return: True if everything goes well False otherwise.
        """
        # TODO implement examining toc files for multipackage tests.
        if self.toc_files:
            return self._test_logs()
        return True

    def _find_exepath(self, test):
        """
        Search for all executables generated by the testcase.

        If the test-case is called e.g. 'test_multipackage1', this is
        searching for each of 'test_multipackage1.exe' and
        'multipackage1_?.exe' in both one-file- and one-dir-mode.
        """
        assert test.startswith('test_')
        name = test[5:] + '_?'
        parent_dir = self._distdir
        patterns = [
            # one-file deploy pattern
            os.path.join(parent_dir, test+'.exe'),
            # one-dir deploy pattern
            os.path.join(parent_dir, test, test+'.exe'),
            # search for e.g. `multipackage2_B`, too:
            os.path.join(parent_dir, name+'.exe'),
            os.path.join(parent_dir, name, name+'.exe'),
            ]
        for pattern in patterns:
            for prog in glob.glob(pattern):
                if os.path.isfile(prog):
                    yield prog

    def _run_created_exe(self, prog):
        """
        Run executable created by PyInstaller.
        """
        # Run the test in a clean environment to make sure they're
        # really self-contained
        path = compat.getenv('PATH')
        compat.unsetenv('PATH')
        # For Windows we need to keep minimal PATH for sucessful running of some tests.
        if is_win:
            # Minimum Windows PATH is in most cases:   C:\Windows\system32;C:\Windows
            compat.setenv('PATH', os.pathsep.join(winutils.get_system_path()))

        self._plain_msg("RUNNING: " + prog)
        old_wd = compat.getcwd()
        os.chdir(os.path.dirname(prog))
        # Run executable.
        prog = os.path.join(os.curdir, os.path.basename(prog))
        proc = subprocess.Popen([prog], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Prints stdout of subprocess continuously.
        self._msg('STDOUT %s' % self.test_name)
        while proc.poll() is None:
            #line = proc.stdout.readline().strip()
            line = proc.stdout.read(1)
            self._plain_msg(line.decode('utf-8'), newline=False)
        # Print any stdout that wasn't read before the process terminated.
        # See the conversation in https://github.com/pyinstaller/pyinstaller/pull/1092
        # for examples of why this is necessary.
        self._plain_msg(proc.stdout.read().decode('utf-8'), newline=False)
        # Print possible stderr at the end.
        stderr = proc.stderr.read().decode('utf-8')
        self._msg('STDERR %s' % self.test_name)
        self._plain_msg(stderr)
        compat.setenv("PATH", path)
        # Restore current working directory
        os.chdir(old_wd)
        return proc.returncode, stderr

    def _test_building(self):
        """
        Run building of test script.

        Return True if build succeded False otherwise.
        """
        OPTS = ['--debug', '--noupx',
                '--specpath', self._specdir,
                '--distpath', self._distdir,
                '--workpath', self._builddir]
        OPTS.extend(['--debug', '--log-level=INFO'])
        OPTS.append('--onedir')

        pyi_args = [self.script] + OPTS
        # TODO fix return code in running PyInstaller programatically
        PYI_CONFIG = configure.get_config(upx_dir=None)
        pyi_main.run(pyi_args, PYI_CONFIG)
        retcode = 0

        return retcode == 0

    def test_exe(self):
        """
        Test running of all created executables.

        multipackage-tests generate more than one exe-file and all of
        them have to be run.
        """
        self._msg('EXECUTING TEST ' + self.test_name)
        found = False
        retcode = 0
        stderr = ''
        for exe in self._find_exepath(self.test_file):
            found = True
            rc, err  = self._run_created_exe(exe)
            retcode = retcode or rc
            if rc != 0:
                stderr = '\n'.join((stderr, '--- %s ---' % exe, err))
        if not found:
            self._plain_msg('ERROR: no file generated by PyInstaller found!')
            return 1, list(self._find_exepath(self.test_file))
        return retcode, stderr.strip()


    def _test_logs(self):
        """
        Compare log files (now used only by multipackage test_name).

        Return True if .toc files match or when .toc patters
        are not defined.
        """
        logsfn = glob.glob(self.test_file + '.toc')
        # Other main scripts do not start with 'test_'.
        assert self.test_file.startswith('test_')
        logsfn += glob.glob(self.test_file[5:] + '_?.toc')
        # generate a mapping basename -> pathname
        progs = dict((os.path.splitext(os.path.basename(nm))[0], nm)
                     for nm in self._find_exepath(self.test_file))
        for logfn in logsfn:
            self._msg("EXECUTING MATCHING " + logfn)
            tmpname = os.path.splitext(logfn)[0]
            prog = progs.get(tmpname)
            if not prog:
                return False, 'Executable for %s missing' % logfn
            fname_list = archive_viewer.get_archive_content(prog)
            # the archive contains byte-data, need to decode them
            fname_list = [fn.decode('utf-8') for fn in fname_list]
            pattern_list = eval(open(logfn, 'rU').read())
            # Alphabetical order of patterns.
            pattern_list.sort()
            missing = []
            for pattern in pattern_list:
                for fname in fname_list:
                    if re.match(pattern, fname):
                        self._plain_msg('MATCH: %s --> %s' % (pattern, fname))
                        break
                else:
                    # no matching entry found
                    missing.append(pattern)
                    self._plain_msg('MISSING: %s' % pattern)

            # Not all modules matched.
            # Stop comparing other .toc files and fail the test.
            if missing:
                msg = '\n'.join('Missing %s in %s' % (m, prog)
                                for m in missing)
                return False, msg

        return True, ''


# TODO run by default test as onedir and onefile.
@pytest.fixture
def pyi_builder(tmpdir, monkeypatch):
    tmp = tmpdir.strpath
    # Override default PyInstaller config dir.
    monkeypatch.setenv('PYINSTALLER_CONFIG_DIR', tmp)
    return AppBuilder(tmp)
