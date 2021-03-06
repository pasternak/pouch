#!/usr/bin/env python3
"""bucket"""
import re
import sys
import os
import urllib.request
import tarfile
from zipfile import ZipFile
from urllib.parse import urljoin
from prep import SearchForPackage
from pretty import ProgressBar, Color
from pkg_resources import parse_version
from collections import OrderedDict

PYPI_ENDPOINT = "https://pypi.python.org/simple/"


class DownloadPackage(object):

    def __init__(self, pkg, quiet=False, dependencies=False):
        """
            Download Package class with version check logic
            -
            @pkg - package name to download
            @package - used for OrderedDict and ProgressBar
            @quiet - do not print out any output
            @dependencies - indicator if current downloaded package is a dep
        """
        self.pkg = pkg
        self.package = pkg
        self.quiet = quiet
        self.dependencies = dependencies

    def version_check(self, requested, pkg):
        """Returns version of package which pass
            logical requirements: >,<,<=,>=,==="""
        match = re.match(r'(\w+)(\W+)([\w\.\-]+)', requested)
        package, check, version = None, None, None

        if match:
            package, check, version = match.groups()

        pkg = parse_version(pkg)
        c_pkg = parse_version("{}-{}".format(package, version))
        check_version = {
            None: True,
            ">=": pkg >= c_pkg,
            "<=": pkg <= c_pkg,
            "==": pkg == c_pkg,
            ">": pkg > c_pkg,
            "<": pkg < c_pkg
        }
        return check_version.get(check, None)

    def __unpack(self, members):
        pkg = re.findall(r"\w+", self.pkg)[0]
        for info in members:
            # unpack for both zip and tarfile
            # ZipFile.namelist() returns list of file
            # Tarfile.open returns class with attribute name
            # so for zip: info
            # for tar: info.name points to the same string
            if not hasattr(info, "name"):
                a_file = info             # ZipFile
            else:
                a_file = info.name      # TarFile

            if "/".join(a_file.split("/")[1:]) in [
                "{}.egg-info/requires.txt".format(pkg),
                "requirements.txt"
            ]:
                return info
        return None

    def dependencies_check(self, archive):
        """ Check package dependencies
             look for 'package_name'.egg-info/requires.txt
             or
             requirements.txt
        """
        if archive.endswith(".zip"):
            arch = ZipFile("repo/{}".format(archive)).namelist()
        else:
            arch = tarfile.open("repo/{}".format(archive))
        unpack = self.__unpack(arch)

        # Check if there is no dependencies. If none, return None
        if unpack is None:
            return

        # Dependencies list
        deps = []
        if not archive.endswith(".zip"):
            a_file = arch.extractfile(member=unpack)
        else:
            zip_file = ZipFile("repo/{}".format(archive))
            # Remove [python>= version] version checks
            a_file = zip_file.read(unpack)
            a_file = re.sub(r'\[.*\]', '', a_file.decode('ascii')).split()
        for dep in a_file:
            if hasattr(dep, 'decode'):
                dep = dep.decode('ascii')
            if re.match(r"^\w", dep):
                deps.append(dep)
                download = DownloadPackage(dep, quiet=True, dependencies=True)
                dep = download()
                if dep is not None:
                    deps.extend(dep)
        return deps
        # arch.close()

    def hook(self, count, chunk, total):
        downloaded = int(count * chunk)
        if downloaded > total:
            downloaded = total
        progress[self.package] = (downloaded, total)

    def __download(self):
        package = SearchForPackage(PYPI_ENDPOINT)

        for package, extension, link in \
                package(re.findall(r"\w+", self.pkg)[0]):

            if self.version_check(self.pkg, package):
                self.package = package

                # Normalize PYPI_ENDPOINT URL
                link = urljoin(PYPI_ENDPOINT, link, False)
                link = link.replace("../", "")
                if self.dependencies:
                    info = "  Downloading dependency: {}".format(
                        package, **Color)
                    ProgressBar.set_tab = 0

                else:
                    info = "Requested: {} | Downloading: {}".format(
                        self.pkg.split()[0], package, **Color)
                    ProgressBar.set_tab = 0
                info = info.ljust(50)
                # print(info)
                ProgressBar.text = info
                d_file = "repo/{}.{}".format(package, extension)
                if os.path.exists(d_file) is False:
                    urllib.request.urlretrieve(link, d_file,
                                               reporthook=self.hook)

                urllib.request.urlcleanup()
                return self.dependencies_check("{}.{}".format(
                    package, extension))
                # return True

    def __call__(self):
        return self.__download()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Provide arg!")
        sys.exit(1)
    progress = OrderedDict()
    p_download = DownloadPackage(sys.argv[1])
    p_dep = p_download()
    print(p_dep)
