# Script to overwrite distribution table with table from parent tosca optimization
# Distribution is moved from submit directory, so one level above the
# work directory of the calling job.
# --------------------------------------------------------------------#
import shutil
import os


def main():
    (root, _) = os.path.split(os.getcwd())
    src = os.path.join(root, "tosca_distribution.txt")
    dst = os.getcwd()

    shutil.copy(src, dst)
    os.remove(src)
    print("Moved distribution {} to {}".format(src, dst))


if __name__ == "__main__":
    main()
