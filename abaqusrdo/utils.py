# Utils module for RDO that includes argument parser and
# function to read name of objective function/dresps.
# --------------------------------------------------------------------#
# Imports

import sys
import argparse


# --------------------------------------------------------------------#
def get_arguments():
    """Argument parser for rdo-workflow, arguments are optional so calling
    program is flexible in which arguments to take.
    """
    ap = argparse.ArgumentParser()

    # directories
    ap.add_argument("-id", "--input_dir", type=str, help="Path of Abaqus/Tosca-inputfiles")
    ap.add_argument("-wd", "--work_dir", type=str, help="Tosca work direcory as in ./<input_dir>/<work_dir>")
    ap.add_argument(
        "-rd",
        "--result_dir",
        type=str,
        help="Directory of results from Tosca to read dresps and sensitivities from",
    )
    ap.add_argument(
        "-sd", "--script_dir", type=str, help="Script directory of Isight model and python scripts"
    )

    # job parameter
    ap.add_argument(
        "-j",
        "--job",
        type=str,
        help="Tosca job name for extraction of DRESPs from parameter-file",
    )
    ap.add_argument("-c", "--cycle", type=int, help="Design cycle passed by Tosca automatically")
    ap.add_argument(
        "-r",
        "--run",
        type=int,
        help="Iteration of Tosca within Isight-loop, 0 being the reference-model.",
    )

    args, _ = ap.parse_known_args(args=None if sys.argv[1:] else ["-h"])

    return args


def read_names(output_file):
    """This function takes the report file of a Tosca job and returns
    the name of the objective function and all constraints.
    """
    names = []
    identifier = ["[OBJ_FUNC]", "[CON]"]

    for cell_content in output_file[0]:
        name = cell_content.strip()
        if identifier[0] in name:
            names.append(name)
        if identifier[1] in name:
            name = name.split(":")[0]
            names.append(name)
    return names
