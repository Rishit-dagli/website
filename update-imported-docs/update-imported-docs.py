#!/usr/bin/env python3
##
# This script was tested with Python 3.7.4, Go 1.14.4+, and PyYAML 5.1.2
# installed in a virtual environment.
# This script assumes you have the Python package manager 'pip' installed.
#
# This script updates the generated reference documentation.
# See https://kubernetes.io/docs/contribute/generate-ref-docs/kubernetes-components/
# for further details.
#
# This script checks to make sure Go and PyYAML have been installed.
# The reference docs are generated by a Go command so the Go binary must be
# in your PATH.
#
# A temp "work_dir" is created and is the path where repos will be cloned.
# The work_dir is printed out so you can remove it
# when you no longer need the contents.
# This work_dir will temporarily become the GOPATH.
#
# To execute the script from the website/update-imported-docs directory:
# ./update-imported-docs.py <config_file> <k8s_release>
# Config files:
#     reference.yml  use this to update the reference docs
#     release.yml    use this to auto-generate/import release notes
# K8S_RELEASE: provide a valid release tag such as, 1.17.0
##

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import platform

error_msgs = []

# pip should be installed when Python is installed, but just in case...
if not (shutil.which('pip') or shutil.which('pip3')):
    error_msgs.append(
        "Install pip so you can install PyYAML. https://pip.pypa.io/en/stable/installing")

reqs = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
installed_packages = [r.decode().split('==')[0] for r in reqs.split()]
if 'PyYAML' not in installed_packages:
    error_msgs.append(
        "Please ensure the PyYAML package is installed; see https://pypi.org/project/PyYAML")
else:
    import yaml

if not shutil.which('go'):
    error_msgs.append(
        "Go must be installed. See https://golang.org/doc/install")


def process_links(content, remote_prefix, sub_path):
    """Process markdown links found in the docs."""

    def analyze(match_obj):
        ankor = match_obj.group('ankor')
        target = match_obj.group('target')
        if not (target.startswith("https://") or
                target.startswith("mailto:") or
                target.startswith("#")):
            if target.startswith("/"):
                target_list = remote_prefix, target[1:]
                target = "/".join(target_list)
            else:
                target_list = remote_prefix, sub_path, target
                target = "/".join(target_list)

        return "[%s](%s)" % (ankor, target)

    # Links are in the form '[text](url)'
    link_regex = re.compile(r"\[(?P<ankor>.*)\]\((?P<target>.*)\)")
    content = re.sub(link_regex, analyze, content)

    h1_regex = re.compile("^(# .*)?\n")
    content = re.sub(h1_regex, "", content)

    return content


def process_kubectl_links(content):
    """Update markdown links found in the SeeAlso section of kubectl page.
       Example:[kubectl annotate](/docs/reference/generated/kubectl/kubectl-commands#annotate)
    """

    def analyze(match_obj):
        ankor = match_obj.group('ankor')
        target = match_obj.group('target')
        if target.endswith(".md") and target.startswith("kubectl"):
            ankor_list = ankor.split("kubectl ")
            target = "/docs/reference/generated/kubectl/kubectl-commands" + "#" + \
                     ankor_list[1]
        return "[%s](%s)" % (ankor, target)

    # Links are in the form '[text](url)'
    link_regex = re.compile(r"\[(?P<ankor>.*)\]\((?P<target>.*?)\)")
    content = re.sub(link_regex, analyze, content)

    return content


def process_file(src, dst, repo_path, repo_dir, root_dir, gen_absolute_links):
    """Process a file element.

    :param src: A string containing the relative path of a source file. The
        string may contain wildcard characters such as '*' or '?'.
    :param dst: The path for the destination file. The string can be a
        directory name or a file name.
    :param repo_path:
    :param repo_dir:
    :param root_dir:
    :param gen_absolute_links:
    """
    pattern = os.path.join(repo_dir, repo_path, src)
    dst_path = os.path.join(root_dir, dst)

    for src in glob.glob(pattern):
        # we don't dive into subdirectories
        if not os.path.isfile(src):
            print("[Error] skipping non-regular path {}".format(src))
            continue

        content = ""
        try:
            with open(src, "r") as srcFile:
                content = srcFile.read()
        except Exception as ex:
            print("[Error] failed in reading source file: ".format(ex))
            continue

        dst = dst_path
        if dst_path.endswith("/"):
            base_name = os.path.basename(src)
            dst = os.path.join(dst, base_name)

        try:
            print("Writing doc: " + dst)
            with open(dst, "w") as dstFile:
                if gen_absolute_links:
                    src_dir = os.path.dirname(src)
                    remote_prefix = repo_path + "/tree/master"
                    content = process_links(content, remote_prefix, src_dir)
                if dst.endswith("kubectl.md"):
                    print("Processing kubectl links")
                    content = process_kubectl_links(content)
                dstFile.write(content)
        except Exception as ex:
            print("[Error] failed in writing target file {}: {}".format(dst, ex))
            continue


def parse_input_args():
    """
    Parse command line argument
    'config_file' is the first argument; it should be one of the YAML
    files in this same directory
    'k8s_release' is the second argument; provide the release version
    :return: parsed argument
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('config_file', type=str,
                        help="reference.yml to generate reference docs; "
                             "release.yml to generate release notes")
    parser.add_argument('k8s_release', type=str,
                        help="k8s release version, ex: 1.17.0"
                        )
    return parser.parse_args()


def main():
    """The main entry of the program."""
    if len(error_msgs) > 0:
        for msg in error_msgs:
            print(msg + "\n")
        return -2

    # first parse input argument
    in_args = parse_input_args()
    config_file = in_args.config_file
    print("config_file is {}".format(config_file))

    # second parse input argument
    k8s_release = in_args.k8s_release
    print("k8s_release is {}".format(k8s_release))

    # if release string does not contain patch num, add zero
    if len(k8s_release) == 4:
        k8s_release = k8s_release + ".0"
        print("k8s_release updated to {}".format(k8s_release))

    curr_dir = os.path.dirname(os.path.abspath(__file__))
    print("curr_dir {}".format(curr_dir))
    root_dir = os.path.realpath(os.path.join(curr_dir, '..'))
    print("root_dir {}".format(root_dir))

    try:
        config_data = yaml.full_load(open(config_file, 'r'))
    except Exception as ex:
        # to catch when a user specifies a file that does not exist
        print("[Error] failed in loading config file - {}".format(str(ex)))
        return -2

    os.chdir(root_dir)

    # create the temp work_dir
    try:
        print("Making temp work_dir")
        work_dir = tempfile.mkdtemp(
            dir='/tmp' if platform.system() == 'Darwin' else tempfile.gettempdir()
        )
    except OSError as ose:
        print("[Error] Unable to create temp work_dir {}; error: {}"
              .format(work_dir, ose))
        return -2

    print("Working dir {}".format(work_dir))

    for repo in config_data["repos"]:
        if "name" not in repo:
            print("[Error] repo missing name")
            continue
        repo_name = repo["name"]

        if "remote" not in repo:
            print("[Error] repo {} missing repo path".format(repo_name))
            continue
        repo_remote = repo["remote"]

        remote_regex = re.compile(r"^https://(?P<prefix>.*)\.git$")
        matches = remote_regex.search(repo_remote)
        if not matches:
            print("[Error] repo path for {} is invalid".format(repo_name))
            continue

        repo_path = os.path.join("src", matches.group('prefix'))

        os.chdir(work_dir)
        print("Cloning repo {}".format(repo_name))
        cmd = "git clone --depth=1 -b {0} {1} {2}".format(
            repo["branch"], repo_remote, repo_path)
        res = subprocess.call(cmd, shell=True)
        if res != 0:
            print("[Error] failed in cloning repo {}".format(repo_name))
            continue

        os.chdir(repo_path)
        if "generate-command" in repo:
            gen_cmd = repo["generate-command"]
            gen_cmd = "export K8S_RELEASE=" + k8s_release + "\n" + \
                "export GOPATH=" + work_dir + "\n" + \
                "export K8S_ROOT=" + work_dir + \
                "/src/k8s.io/kubernetes" + "\n" + \
                "export K8S_WEBROOT=" + root_dir + "\n" + gen_cmd
            print("Generating docs for {} with {}".format(repo_name, gen_cmd))
            res = subprocess.call(gen_cmd, shell=True)
            if res != 0:
                print("[Error] failed in generating docs for {}".format(
                    repo_name))
                continue

        os.chdir(root_dir)
        for f in repo["files"]:
            process_file(f['src'], f['dst'], repo_path, work_dir, root_dir,
                         "gen-absolute-links" in repo)

    print("Completed docs update. Now run the following command to commit:\n\n"
          " git add .\n"
          " git commit -m <comment>\n"
          " git push\n"
          " delete temp dir {} when done ".format(work_dir))


if __name__ == '__main__':
    sys.exit(main())
