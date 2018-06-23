import os
import subprocess
import git
import yaml

ska_conda_path = os.path.abspath(os.path.dirname(__file__))
pkg_defs_path = os.path.join(ska_conda_path, "pkg_defs")
build_list = os.path.join(ska_conda_path, "build_order.txt")

class SkaBuilder(object):

    def __init__(self, ska_root=None):
        if ska_root is None:
            ska_root = "/tmp/ska3_pkg/"
        self.ska_root = ska_root
        self.ska_build_dir = os.path.join(self.ska_root, "builds")
        self.ska_src_dir = os.path.join(self.ska_root, "src")
        os.environ["SKA_TOP_SRC_DIR"] = self.ska_src_dir

    def _clone_repo(self, name, tag=None):
        if name == "ska":
            return
        print("Cloning source %s." % name)
        clone_path = os.path.join(self.ska_src_dir, name)
        if not os.path.exists(clone_path):
            # Try ssh first to avoid needing passwords for the private repos
            # We could add these ssh strings to the meta.yaml for convenience
            try:
                git_ssh_path = 'git@github.com:sot/' + name + '.git'
                repo = git.Repo.clone_from(git_ssh_path, clone_path)
                assert not repo.bare
            except:
                yml = os.path.join(pkg_defs_path, name, "meta.yaml")
                with open(yml) as f:
                    requires = False
                    while not requires:
                        line = f.readline().strip()
                        if line.startswith("path:"):
                            requires = True
                    data = yaml.load(f)
                    url = data['about']['home']
                repo = git.Repo.clone_from(url, clone_path)
        else:
            repo = git.Repo(clone_path)
        assert not repo.is_dirty()
        # I think we want the commit/tag with the most recent date, though
        # if we actually want the most recently created tag, that would probably be
        # tags = sorted(repo.tags, key=lambda t: t.tag.tagged_date)
        # I suppose we could also use github to get the most recent release (not tag)
        if tag is None:
            tags = sorted(repo.tags, key=lambda t: t.commit.committed_datetime)
            repo.git.checkout(tags[-1].name)
            if tags[-1].commit == repo.heads.master.commit:
                print("Auto-checked out at {} which is also tip of master".format(tags[-1].name))
            else:
                print("Auto-checked out at {} NOT AT tip of master".format(tags[-1].name))
        else:
            repo.git.checkout(tag)
            print("Checked out at {}".format(tag))

    def clone_one_package(self, name, tag=None):
        self._clone_repo(name)

    def clone_all_packages(self):
        with open(build_list, "r") as f:
            for line in f.readlines():
                pkg_name = line.strip()
                if not pkg_name.startswith("#"):
                    self._clone_repo(pkg_name)

    def _get_repo(self, name):
        if name == "ska":
            return None
        repo_path = os.path.join(self.ska_src_dir, name)
        if not os.path.exists(repo_path):
            self._clone_repo(name)
        repo = git.Repo(repo_path)
        return repo

    def _build_package(self, name):
        print("Building package %s." % name)
        pkg_path = os.path.join(pkg_defs_path, name)
        cmd_list = ["conda", "build", pkg_path, "--croot",
                    self.ska_build_dir, "--no-test",
                    "--no-anaconda-upload"]
        subprocess.run(cmd_list)

    def build_one_package(self, name):
        repo = self._get_repo(name)
        if repo is not None:
            repo.remote().pull()
        self._build_package(name)

    def build_updated_packages(self, new_only=True):
        with open(build_list, "r") as f:
            for line in f.readlines():
                pkg_name = line.strip()
                if not pkg_name.startswith("#"):
                    repo = self._get_repo(pkg_name)
                    if repo is None:
                        build = True
                    else:
                        current_tag = repo.tags[-1].name
                        repo.remote().pull()
                        build = repo.tags[-1].name != current_tag
                    if build or not new_only:
                        self._build_package(pkg_name)

    def build_all_packages(self):
        self.build_updated_packages(new_only=False)
