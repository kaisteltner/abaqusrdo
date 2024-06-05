# Module to calculate partial derivatives w.r.t. RVs with FOSM/SOFM
# as well as mean and standard deviation and superimposed
# objective function and/or constraints.
# The module is intended to use as part of the rdo workflow controlled
# from the run_inner_loop.py module and being called by Isight.
# --------------------------------------------------------------------#
# Imports

import csv
import os
import sys
import numpy as np
import shutil
from glob import glob
import utils

# --------------------------------------------------------------------#
# List of elements to write specific sensitivities if running in verbose mode
elements = []  # leave empty to write all dDRESPdDVdRV


# --------------------------------------------------------------------#
def get_covariance(list_RV, verbose):
    """Set up of covarinace matrix. Edit non-diagonal parameters for correlated RVs"""
    r = np.identity(len(list_RV))

    # edit symmetric entries corresponding to problem formulation
    # r[0, 1] = 0.5
    # r[1, 0] = r[0, 1]
    # r[0, 3] = 0.5
    # r[3, 0] = r[0, 3]
    # r[1, 2] = 0.5
    # r[2, 1] = r[1, 2]
    # r[2, 3] = 0.5
    # r[3, 2] = r[3, 2]

    cov = r.copy()
    for i, RV_i in enumerate(list_RV):
        for j, RV_j in enumerate(list_RV):
            cov[i, j] *= RV_i.sigma * RV_j.sigma
    if verbose:
        print("Correlation matrix: ")
        print(r)
        print("Covariance matrix: ")
        print(cov)

    return cov


def get_results(tosca_dirs, verbose):
    """Open optimization_status_*.csv for every finite difference step and read restults."""
    resultsDRESP = []
    resultsSENS = []
    result_dirs = glob(os.path.join(tosca_dirs, "run_*"))
    result_dirs.sort()
    for result_dir in result_dirs:
        results_files = glob(os.path.join(result_dir, "optimization_status*.csv"))
        results_files.sort()
        sens_file = os.path.join(result_dir, "TP_SENS_000.onf")
        resultsDRESP.append([[], [], []])
        for file in results_files:
            with open(file, "r") as resultsfileDRESP:
                listResultsDRESP = list(csv.reader(resultsfileDRESP, delimiter=","))
                for row in range(len(listResultsDRESP)):
                    resultsDRESP[-1][row].extend(listResultsDRESP[row])
        resultsSENS.append([])
        with open(sens_file, "r") as resultsfileSENS:
            for line in resultsfileSENS:
                resultsSENS[-1].append(line)
        if not verbose:
            os.remove(sens_file)
            tosca_dir = [
                os.path.join(result_dir, d)
                for d in os.listdir(result_dir)
                if os.path.isdir(os.path.join(result_dir, d))
            ]
            if tosca_dir and os.path.exists(tosca_dir[0]):
                shutil.rmtree(tosca_dir[0])
    return resultsDRESP, resultsSENS


def write_status(dst, list_DRESP, cycle, kappa):
    """Write csv-file with status of DRESPs including g, mu, sigma, kappa, and cv."""
    file = os.path.join(dst, "DRESP_status_all.csv")

    number_of_dresp = len(list_DRESP)
    all_names = [dresp.name for dresp in list_DRESP]

    header_1 = "ITERATION, KAPPA" + (number_of_dresp * ",{},," + ",\n").format(*all_names)
    header_2 = "," + number_of_dresp * ",DRESP, MU, SIGMA" + ",\n"

    data_line = "{},{}".format(cycle, kappa)
    for dresp in list_DRESP:
        data_line += ",{},{},{}".format(dresp.objective, dresp.mean, dresp.sigma)
    data_line += ",\n"

    if not os.path.exists(file):
        with open(file, "w") as f:
            f.write(header_1 + header_2)
            f.write(data_line)
        print("Created status file {}.".format(file))
    else:
        with open(file, "a") as f:
            f.write(data_line)
        print("Updated status file {}".format(file))


# --------------------------------------------------------------------#
class Dresp(object):
    """Class for DRESP with methods to calculate absolute sensitivities
    from finite differences in RVs"""

    def __init__(self, name, list_RV):
        self.name = name
        self.list_RV = list_RV
        self.numberOfDV = None

        self.mean = None
        self.dmean_dDV = []
        self.sigma = None
        self.dsigma_dDV = []
        self.cv = None
        self.objective = None
        self.dObjective_dDV = []

        self.value = []
        self.dDV = []
        self.dRV = []
        self.ddRV = []
        self.dRVdDV = []
        self.dRVidRVj = []

    def find_values(self, results):
        """Find value of DRESP in data extracted from optimization_status_all.csv as list.
        Input:  results:   list with content of all optimization_status_all.csv
                           results[i] is result file optimization_status_all_i.csv
        """
        # extract final values for DRESP of each tosca run
        for result in results:
            for coloumn, entry in enumerate(result[0]):
                if self.name in entry:
                    self.value.append(float(result[-1][coloumn]))

    def find_sensitivities(self, results):
        """Find sensitivities of DRESP in data extracted from TP_SENS_000.onf as list.
        Input:  results:   list with content of all TP_SENS_000.onf
                           results[i] is result file TP_SENS_000_i.onf
        """
        if "[OBJ_FUNC]" in self.name:
            name = "OBJ_FUNC_SENSITIVITY"
        elif "[CON]" in self.name:
            name = "CONSTRAINT_SENSITIVITY_" + self.name[5:]
        else:
            raise TypeError("Unknown scheme for DRESP name %s!" % self.name)

        # extract number of DV
        lineOfDRESP = [ln for ln, line in enumerate(results[0]) if name in line]
        lineOfDRESP = int(lineOfDRESP[0])
        if self.numberOfDV == None:
            self.numberOfDV = int(results[0][lineOfDRESP + 1])

        # extract sensitivities dDRESP/dDV from full lines in file
        for result in results:
            TP_SENS_list = result[(lineOfDRESP + 2) : (lineOfDRESP + 2 + self.numberOfDV)]
            TP_SENS_rows_split = [row.split(",") for row in TP_SENS_list[:][:]]
            self.dDV.append(np.asarray(TP_SENS_rows_split, dtype=float)[:, 1])

    def calculate_partial_derivatives(self):
        self.__calculate_dRV()
        self.__calculate_dRVdDV()
        if self.list_RV[0].use_central_differences:  # including all second-order approaches
            self.__calculate_ddRV()

    def __calculate_dRV(self):
        """Calculate the derivatives of DRESP wrt. RV"""
        if len(self.list_RV) > 0 and len(self.value) <= 1:
            raise ValueError("Missing results from finite difference steps.")

        for RV in self.list_RV:
            if not RV.use_central_differences:
                if RV.delta != 0:
                    self.dRV.append((1 / RV.delta) * (self.value[RV.forward_step] - self.value[0]))
                else:
                    self.dRV.append(0)
            elif RV.use_central_differences:
                if RV.delta != 0:
                    self.dRV.append(
                        (1 / (2 * RV.delta)) * (self.value[RV.forward_step] - self.value[RV.backward_step])
                    )
                else:
                    self.dRV.append(0)
        return self.dRV

    def __calculate_dRVdDV(self):
        """Calculate the derivatives of dDRESPdDV wrt. RV"""
        if len(self.list_RV) > 0 and len(self.dDV) <= 1:
            raise ValueError("Missing results from finite difference steps.")

        for RV in self.list_RV:
            if not RV.use_central_differences:
                if RV.delta != 0:
                    self.dRVdDV.append((1 / RV.delta) * (self.dDV[RV.forward_step] - self.dDV[0]))
                else:
                    self.dRVdDV.append(np.zeros_like(self.dDV[0]))
            elif RV.use_central_differences:
                if RV.delta != 0:
                    self.dRVdDV.append(
                        (1 / (2 * RV.delta)) * (self.dDV[RV.forward_step] - self.dDV[RV.backward_step])
                    )
                else:
                    self.dRVdDV.append(np.zeros_like(self.dDV[0]))
        return self.dRVdDV

    def __calculate_ddRV(self):
        """Calculate the second-order derivatives of DRESP"""
        for RV in self.list_RV:
            if RV.delta != 0:
                self.ddRV.append(
                    (1 / (RV.delta**2))
                    * (self.value[RV.forward_step] - 2 * self.value[0] + self.value[RV.backward_step])
                )
            else:
                self.ddRV.append(0)
        return self.ddRV

    def calculate_objective(self, cov, kappa):
        """Calculate mean, sigma, objective and its derivative of DRESP."""
        var = 0
        dvar_dDV = [0]

        self.mean = self.value[0]  # DRESP at mean of RVs
        self.dmean_dDV = self.dDV[0]

        for i in [RV.idx for RV in self.list_RV]:
            # Correlated random variables
            if not np.allclose(cov * np.linalg.inv(cov), np.identity(cov.shape[0])):
                for j in [RV.idx for RV in self.list_RV if RV.idx >= i]:
                    # j loop for considering correlation in fosm-variance
                    var_loop = (self.dRV[i] * self.dRV[j]) * cov[i][j]
                    dvar_loop = 2 * (np.multiply(self.dRVdDV[i], self.dRV[j]) * cov[i][j])
                    var += var_loop
                    dvar_dDV += dvar_loop
            else:
                # default: uncorrelated random variables
                var += (self.dRV[i] ** 2) * cov[i][i]
                dvar_dDV += 2 * self.dRV[i] * self.dRVdDV[i] * cov[i][i]

        self.sigma = np.sqrt(var)
        if var > 0:
            self.dsigma_dDV = np.multiply(1 / (2.0 * self.sigma), dvar_dDV)
        else:
            self.dsigma_dDV = np.multiply(0, dvar_dDV)
        self.cv = self.sigma / self.mean

        self.objective = self.mean + kappa * self.sigma
        self.dObjective_dDV = self.dmean_dDV + kappa * self.dsigma_dDV

    def write_output(self, dst, elements=[], use_central_differences=True, verbose=False):
        """Write output of current cycle to Isight-work directory and parent Tosca work directory.
            Output to be written:
        DRESP_<name>.ONF:        DRESP value and sensitivities for parent optimization
        DRESP_<name>_status.csv: Table with status of all cycles for DRESP"""
        self.__write_ONF(dst, verbose)
        self.__write_sensitivities(dst, elements, use_central_differences, verbose)

    def __write_ONF(self, dst, verbose):
        """Write approximation of DRESP and its sensitivities to ONF file to be used in subsequent optimization."""
        file = os.path.join(dst, "DRESP_{}.onf".format(self.name))
        with open(file, "w") as f:
            f.write("# Data block 640 - Optimization Results - Elemental scalar value\n   -1\n   640\n1\n")
            f.write("1, {:E}\n   -1\n".format(self.objective))
            f.write("# Data block 642 - Optimization Results - Elemental scalar value\n   -1\n   642\n")
            f.write("{:d}\n".format(self.numberOfDV))
            for num, entry in enumerate(self.dObjective_dDV):
                f.write("{:d}, {:07E}\n".format(num + 1, entry))
            f.write("   -1")
        if verbose:
            print("Saved output file {}".format(file))

    def __write_sensitivities(self, dst, elements, use_central_differences, verbose):
        """Debug function to output derivatives to "dresp_sensitivities_<name>.csv",
        writing only der. if dresp, mean and sigma w.r.t. DV.
        """
        sens_file = os.path.join(dst, "dresp_sensitivities_{}.csv".format(self.name))

        with open(sens_file, "w") as f:
            if use_central_differences == False:
                rv_indices = 2 * [RV.idx + 1 for RV in self.list_RV]
                rv_indices.sort()

                f.write(
                    ",dresp, mean, sig, ,g_mu"
                    + (max(rv_indices) * ", ,g_z{}_forw, dg_dz{}").format(*rv_indices)
                    + "\n"
                )
                data_line = ",{},{},{}, ,{}".format(self.objective, self.mean, self.sigma, self.value[0])
                for RV in self.list_RV:
                    data_line += ", ,{},{}".format(self.value[RV.idx + 1], self.dRV[RV.idx])
                data_line += "\n\n"
                f.write(data_line)
            elif use_central_differences == True:
                rv_indices = 3 * [RV.idx + 1 for RV in self.list_RV]
                rv_indices.sort()

                f.write(
                    ",dresp, mean, sig, ,g_mu"
                    + (max(rv_indices) * ", ,g_z{}_back, g_z{}_forw, dg_dz{}").format(*rv_indices)
                    + "\n"
                )
                data_line = ",{},{},{}, ,{}".format(self.objective, self.mean, self.sigma, self.value[0])
                for RV in self.list_RV:
                    data_line += ", ,{},{},{}".format(
                        self.value[2 * RV.idx + 1],
                        self.value[2 * RV.idx + 2],
                        self.dRV[RV.idx],
                    )
                f.write(data_line)

        if verbose:
            with open(sens_file, "a") as f:
                f.write("\n\ne, ddresp, dmean, dsig\n")
                data_line = "{},{},{},{}\n"
                if len(elements) > 0:
                    for e in elements:
                        f.write(
                            data_line.format(
                                e,
                                self.dObjective_dDV[e - 1],
                                self.dmean_dDV[e - 1],
                                self.dsigma_dDV[e - 1],
                            )
                        )
                else:
                    for e in range(self.numberOfDV):
                        f.write(
                            data_line.format(
                                e + 1,
                                self.dObjective_dDV[e],
                                self.dmean_dDV[e],
                                self.dsigma_dDV[e],
                            )
                        )

    def write_raw(self, dst):
        """Write out content read from tosca/abaqus for debugging purposes."""
        file = os.path.join(dst, "DRESP_{}_raw.csv".format(self.name))
        with open(file, "w") as f:
            runs = len(self.value)
            header = (", run {:02d}" * runs).format(*list(range(runs)))
            f.write(header + "\n")
            data_placeholder = ", {}" * runs + "\n"
            f.write("ELEMENT" + data_placeholder.format(*self.value))
            data_placeholder = "{}" + data_placeholder
            for idx in range(len(self.dDV[0])):
                dDVs = [dDV[idx] for dDV in self.dDV]
                f.write(data_placeholder.format(idx + 1, *dDVs))


class RV(object):
    """Class for robustness variable"""

    delta = 0

    def __init__(self, idx, mean, sigma, delta, use_central_differences):
        self.idx = idx
        self.mean = float(mean)
        self.sigma = float(sigma)
        self.delta = float(delta)
        self.use_central_differences = use_central_differences
        if self.use_central_differences:
            self.forward_step = 2 * (idx + 1)
            self.backward_step = 2 * (idx + 1) - 1
        else:
            self.forward_step = idx + 1

    def __str__(self):
        msg = """Robustness Variable with parameters:\n
                \tMean: {}\n\tSigma: {}\n\tDelta: {}
                """.format(
            self.mean, self.sigma, self.delta
        )
        return msg


# --------------------------------------------------------------------#
# MAIN
def main():
    args = utils.get_arguments()

    # Get parameters for RVs
    sys.path.append(args.input_dir)
    import config_rdo as cfg

    rdo_work_dir = os.path.join(args.input_dir, "{}_RDO".format(args.job))
    tosca_dirs = os.path.join(rdo_work_dir, "inner_loop", "{:s}_{:03d}".format(args.job, args.cycle), "tosca")

    # ------------------------------------------------------------------------------------#
    # Create objects for RVs and read results
    list_RV = [
        RV(i, cfg.mean_rv[i], cfg.sigma_rv[i], cfg.delta_rv[i], cfg.use_central_differences)
        for i in range(cfg.number_of_rv)
    ]
    cov = get_covariance(list_RV, cfg.verbose)

    resultsDRESP, resultsSENS = get_results(tosca_dirs, cfg.verbose)

    # ------------------------------------------------------------------------------------#
    # Create objects for DRESPs, read results and calculate partial derivatives wrt RVs
    # get DRESPS
    names = utils.read_names(resultsDRESP[0])
    list_DRESP = [Dresp(name, list_RV) for name in names if "VOL" not in name if "MASS" not in name]
    for dresp in list_DRESP:
        dresp.find_values(resultsDRESP)
        dresp.find_sensitivities(resultsSENS)
        if cfg.verbose:
            dresp.write_raw(args.result_dir)
        dresp.calculate_partial_derivatives()
        dresp.calculate_objective(cov, float(cfg.kappa))
        dresp.write_output(
            dst=args.result_dir,
            elements=elements,
            use_central_differences=cfg.use_central_differences,
            verbose=cfg.verbose,
        )
    write_status(rdo_work_dir, list_DRESP, args.cycle, cfg.kappa)

    # Remove automatically generated python files for config
    files = [
        os.path.join(args.input_dir, "config_rdo$py.class"),
        os.path.join(args.input_dir, "config_rdo.pyc"),
        os.path.join(args.input_dir, "__pycache__")
    ]
    for fi in files:
        if os.path.exists(fi):
            if os.path.isdir(fi):
                shutil.rmtree(fi)
            else:
                os.remove(fi)

if __name__ == "__main__":
    main()
