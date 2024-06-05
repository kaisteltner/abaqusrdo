# Main module for RDO workflow. This module sets up the directory structre
# and launches the Isight model for the inner loop. After the loop is done,
# the results are copied to the parent Tosca work dir for the RDO.
# --------------------------------------------------------------------#
# Imports

import sys
import os
import shutil
import glob
import utils
import subprocess as sp


# --------------------------------------------------------------------#
# Scripts and classes
def create_dir(path, verbose):
    """Creates directory in path if it doesn't exist."""
    if not os.path.exists(path):
        os.mkdir(path)
        if verbose:
            print("Successfully created directory {}".format(path))


class IsightJob:
    """IsightJob class for Isight job to perform finite difference-steps in RV
    and calculate DRESP + sensitivities
    """

    def __init__(
        self,
        input_dir,
        script_dir,
        tosca_work_dir,
        job_name,
        number_of_rv,
        mean_rv,
        sigma_rv,
        delta_rv,
        kappa,
        use_central_differences,
        run_on_windows,
        cycle,
        verbose,
    ):
        """Create job-object for Isight loop."""
        self.job_name = job_name
        self.number_of_rv = int(number_of_rv)
        self.mean_rv = mean_rv
        self.sigma_rv = sigma_rv
        self.delta_rv = delta_rv
        self.kappa = kappa
        self.verbose = verbose

        self.use_central_differences = use_central_differences
        self.run_on_windows = run_on_windows

        self.cycle = cycle
        self._setup_directories(input_dir, script_dir, tosca_work_dir)
        self._clean_input()
        self._clean_inner_loop()

    def _setup_directories(self, input_dir, script_dir, tosca_work_dir):
        """Setup of directories for current Isight-run."""
        self.script_dir = script_dir
        self.input_dir = input_dir
        self.tosca_work_dir = tosca_work_dir

        # work directory for Isight-iteration within Tosca (RDO) work dir
        self.isight_root_dir = os.path.join(self.tosca_work_dir, "inner_loop")
        create_dir(self.isight_root_dir, self.verbose)
        self.isight_work_dir = os.path.join(
            self.isight_root_dir, self.job_name + "_{:03d}".format(self.cycle)
        )
        create_dir(self.isight_work_dir, self.verbose)

        # directory for processed results of inner loop
        self.result_dir = os.path.join(self.isight_work_dir, "sensitivities")
        create_dir(self.result_dir, self.verbose)

        # run directories for Tosca (adjoint sensitivities) in Isight-loop
        self.tosca_dir = os.path.join(self.isight_work_dir, "tosca")
        create_dir(self.tosca_dir, self.verbose)

        self.runtime_dir = []

        if self.use_central_differences:
            total_runs = 2 * self.number_of_rv + 1
        else:
            total_runs = self.number_of_rv + 1

        for run in range(total_runs):
            rt_dir = os.path.join(self.tosca_dir, "run_{:03d}".format(run))
            create_dir(rt_dir, self.verbose)
            self.runtime_dir.append(rt_dir)
        sys.stdout.flush()

    def _clean_input(self):
        """Delete DRESPs of previous cycle from work_dir."""
        previous_results = glob.glob(os.path.join(self.tosca_work_dir, "DRESP_*.onf"))
        for file in previous_results:
            os.remove(file)

    def _clean_inner_loop(self):
        """Delete previous directory in subdirectory inner_loop."""
        if self.verbose:
            print("Running in verbose mode, keeping all directories in inner_loop.")
        elif not self.verbose and self.cycle > 1:
            previous_dir = os.path.join(
                self.isight_root_dir,
                self.job_name + "_{:03d}".format((int(self.cycle) - 1)),
            )
            shutil.rmtree(previous_dir)

    def _move_results(self):
        """Move results from result dir to parent Tosca work dir."""
        print("Moving files containing DRESPs and sensitvities to Tosca work dir.", flush=True)
        result_files = glob.glob(os.path.join(self.result_dir, "DRESP_*.onf"))
        for rf in result_files:
            dst = os.path.join(self.tosca_work_dir, os.path.split(rf)[1])
            if self.verbose:
                shutil.copy2(rf, self.tosca_work_dir)
            else:
                shutil.move(rf, dst)

    def info(self):
        """Display job attributes in terminal -> TOSCA.OUT."""
        print(
            "#------------------------------------------------------------------------------------------------------------------#"
        )
        print(
            "                         Inner loop for robustness determination - Cycle {}".format(self.cycle)
        )
        print(
            "#------------------------------------------------------------------------------------------------------------------#"
        )
        print("Tosca-cycle: {:d}".format(self.cycle))
        print("Work directory for job is {:s}".format(self.isight_work_dir))
        print("Number of random variables: {:d}".format(self.number_of_rv))
        print("Mean values for random variables: {}".format(self.mean_rv))
        print("Standard deviation of random variables: {}".format(self.sigma_rv))
        print("Kappa for robust design response: {:.2f}".format(self.kappa))
        print("Delta for finite differences in inner loop: {}".format(self.delta_rv))
        if self.use_central_differences:
            print("Using central differences for sensitivities with respect to random variables.")
        print(
            "#------------------------------------------------------------------------------------------------------------------#"
        )
        sys.stdout.flush()

    def start(self):
        """Start Isight model for adjoint sensitivities calculation."""
        isight_model_path = os.path.join(self.input_dir, "inner_loop.zmf")
        isight_output_file_path = os.path.join(self.isight_work_dir, "isight_out.txt")
        isight_log_path = os.path.join(self.isight_work_dir, "isight_log.log")
        isight_call = (
            "fipercmd logonprompt:no nogui:true profile:standalone "
            'loglevel:info logfile:"{}" start file:"{}" '
            'monitor:y output:"{}" '.format(isight_log_path, isight_model_path, isight_output_file_path)
        )
        isight_args_directories = 'args:"input_dir={};script_dir={};' "tosca_dir={};result_dir={};".format(
            self.input_dir, self.script_dir, self.tosca_dir, self.result_dir
        )
        isight_args_job = 'job={};cycle={};verbose={}"'.format(
            self.job_name,
            self.cycle,
            self.verbose,
        )
        complete_isight_call = isight_call + isight_args_directories + isight_args_job
        if self.verbose:
            print(complete_isight_call, flush=True)

        cp = sp.run(complete_isight_call, shell=True, check=True)
        self._move_results()


# --------------------------------------------------------------------#
def main():
    # Get arguments from module call
    args = utils.get_arguments()

    input_dir = args.input_dir.strip('"')
    script_dir = args.script_dir.strip('"')
    tosca_work_dir = os.path.join(input_dir, "{}_RDO".format(args.job))

    # Get parameters from config file
    sys.path.append(input_dir)
    import config_rdo as cfg

    # Setup Isight job and start
    job = IsightJob(
        input_dir,
        script_dir,
        tosca_work_dir,
        args.job,
        cfg.number_of_rv,
        cfg.mean_rv,
        cfg.sigma_rv,
        cfg.delta_rv,
        cfg.kappa,
        cfg.use_central_differences,
        cfg.run_on_windows,
        args.cycle,
        cfg.verbose,
    )

    job.info()
    job.start()


# --------------------------------------------------------------------#
# Execution as main
if __name__ == "__main__":
    main()
