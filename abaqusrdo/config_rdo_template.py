# Provide data for random variables. All values have to be defined.
# Mean, sigma and delta have to be given per RV

number_of_rv = 2

mean_rv = number_of_rv * [100]      # Or rv-specific: [100, 110]
sigma_rv = number_of_rv * [1000]    # Or rv-specific: [1000, 900]
delta_rv = number_of_rv * [1500]    # Or rv-specific: [1400, 1600]

use_central_differences = False
kappa = 1

# Set to true if running on windows machine, false if running on linux

run_on_windows = True

# Set to true for additional debug output

verbose = True