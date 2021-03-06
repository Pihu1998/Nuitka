#     Copyright 2019, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Utils for file and directory operations.

This provides enhanced and more error resilient forms of standard
stuff. It will also frequently add sorting.

"""

import os
import shutil
import tempfile
import time
from contextlib import contextmanager

from .ThreadedExecutor import Lock
from .Utils import getOS

# Locking seems to be only required for Windows currently, expressed that in the
# lock name.
file_lock = None


@contextmanager
def _with_file_Lock():
    # This is a singleton, pylint: disable=global-statement
    global file_lock

    if file_lock is None:
        file_lock = Lock()

    file_lock.acquire()
    yield
    if file_lock is not None:
        file_lock.release()


def areSamePaths(path1, path2):
    """ Are two paths the same.

    Same meaning here, that case differences ignored on platforms where
    that is the norm, and with normalized, and turned absolute paths,
    there is no differences.
    """

    path1 = os.path.normcase(os.path.abspath(os.path.normpath(path1)))
    path2 = os.path.normcase(os.path.abspath(os.path.normpath(path2)))

    return path1 == path2


def relpath(path):
    """ Relative path, if possible. """

    try:
        return os.path.relpath(path)
    except ValueError:
        # On Windows, paths on different devices prevent it to work. Use that
        # full path then.
        if getOS() == "Windows":
            return os.path.abspath(path)
        raise


def makePath(path):
    """ Create a directory if it doesn'T exist."""

    with _with_file_Lock():
        if not os.path.isdir(path):
            os.makedirs(path)


def listDir(path):
    """ Give a sorted path, base filename pairs of a directory."""

    return sorted(
        [(os.path.join(path, filename), filename) for filename in os.listdir(path)]
    )


def getFileList(path):
    result = []

    for root, _dirnames, filenames in os.walk(path):
        for filename in filenames:
            result.append(os.path.join(root, filename))

    return result


def getSubDirectories(path):
    result = []

    for root, dirnames, _filenames in os.walk(path):
        for dirname in dirnames:
            result.append(os.path.join(root, dirname))

    result.sort()
    return result


def deleteFile(path, must_exist):
    with _with_file_Lock():
        if must_exist or os.path.isfile(path):
            os.unlink(path)


def splitPath(path):
    """ Split path, skipping empty elements. """
    return tuple(element for element in os.path.split(path) if element)


def hasFilenameExtension(path, extensions):
    extension = os.path.splitext(os.path.normcase(path))[1]

    return extension in extensions


def removeDirectory(path, ignore_errors):
    """ Remove a directory recursively.

        On Windows, it happens that operations fail, and succeed when reried,
        so added a retry and small delay, then another retry. Should make it
        much more stable during tests.

        All kinds of programs that scan files might cause this, but they do
        it hopefully only briefly.
    """

    def onError(func, path, exc_info):
        # Try again immediately, ignore what happened, pylint: disable=unused-argument
        try:
            func(path)
        except OSError:
            time.sleep(0.1)

        func(path)

    with _with_file_Lock():
        if os.path.exists(path):
            try:
                shutil.rmtree(path, ignore_errors=False, onerror=onError)
            except OSError:
                if ignore_errors:
                    shutil.rmtree(path, ignore_errors=ignore_errors)
                else:
                    raise


@contextmanager
def withTemporaryFile(suffix="", mode="w", delete=True):
    with tempfile.NamedTemporaryFile(
        suffix=suffix, mode=mode, delete=delete
    ) as temp_file:
        yield temp_file


def getFileContentByLine(filename, mode="r"):
    with open(filename, mode) as f:
        return f.readlines()


def getFileContents(filename):
    with open(filename, "r") as f:
        return f.read()


def renameFile(source_filename, dest_filename):
    # There is no way to safely uodatea file on Windows, but lets
    # try on Linux at least.
    old_stat = os.stat(source_filename)

    try:
        os.rename(source_filename, dest_filename)
    except OSError:
        shutil.copyfile(source_filename, dest_filename)
        os.unlink(source_filename)

    os.chmod(dest_filename, old_stat.st_mode)
