User guide
==========

This document lists the files and file structure required for performing the RDO, the changes required for the RDO workflow, as well as instructions for the execution.

Prerequisites
-------------

- Add ``<Tosca_install_dir>/<os>/code/command`` to ``PATH`` environment variable
- Add ``<Isight_install_dir>/<os>/code/command`` to ``PATH`` environment variable

The code is written to launch Abaqus, Tosca and Isight from the command line using the comands ``abaqus``, ``ToscaStructure`` and ``fipercmd``, respectively. Adding the aforementioned paths to ``PATH`` ensures that these commands launch the respective programs.

Setup
-----------------------

The root directory of the optimization is refered to as ``<input>``, the optimization ID or name itself is refered to as ``<job>``. All Abaqus/Tosca related input files are placed in the ``<input>`` directory. Mind that the ID has to be identical for all ``.inp`` and ``.par``-files as indicated. Additionally, the job-specific files ``config_rdo.py`` and ``inner_loop.zmf`` are placed at the same root level. The ``script_directory`` may be placed within ``<input>``, but it can also exist elsewhere, as the modules within are job-independent.

.. code::

    <input>
    ├── <job>.inp
    ├── <job>.par
    ├── <job>_RDO.par
    ├── ... additional job specific files
    ├── config_rdo.py
    ├── inner_loop.zmf
    ├── <script_directory>
        ├── calculate_derivatives.py
        ├── get_distribution.py
        ├── run_inner_loop.py
        ├── utils.py

The following files have to be modified job-specifically for running the RDO:

- ``<job>.inp`` Adjust the file to incorporate parameters for the random variables (RVs). Ideally, RVs are discrete values in the input file to be modified directly within the Isight execution, but other formulations using, e.g., previously generated files and copy rules are also possible. 
- ``<job>.par`` Tosca input file for the inner loop, modified from the default Tosca input file. The optimization needs to be fully defined for Tosca to run. No iterations are performed, only the solver will be called to calculate and write out adjoint sensitivies. The actual design responses are defined here. The software reads only the objective function or constraint-values. The ID_NAMEs of the objective function and constraints, respectively, are used to define design responses (DRESPs) in ``<job>_RDO.par``. Mass or volume are not available for robustness consideration but can be considered as usual in ``<job>_RDO.par``. RDO specific modifications:

    - ``DRIVER`` block: Calls Python script ``get_distribution.py`` to copy distribution table for design variables (DVs) from outer loop. Make sure to define ``script_directory``::

            DRIVER
                ! SET DIRECTORY FOR PYTHON-SCRIPTS/ISIGHT-MODEL
                script_directory = r'/path/to/<script_directory>'
                ! GET tosca_distribution.txt FROM PARENT TOSCA DESIGN CYCLE 
                driver.registerModuleHook(ToscaModules.FEM_MODIF, HookTypes.PRE, EventTimes.FIRST, f'"{script_directory}/get_distribution.py"', addIterPert=False)
            END_

    - ``USER_FILE`` block: Save adjoint sensitivites to ``TP_SENS_-.onf``::
            
            USER_FILE
                ID_NAME     = UF_TOPO_ONF_SENS
                FORMAT      = ONF
                EL_GROUP    = ALL_ELEMENTS
                TYPE        = TOPO_WITH_SENS
                FILE_NAME   = TP_SENS
                WRITE       = EVER
                FILE_OPTION = VAR2
            END_

    - ``STOP``: Add stop condition so no optimization is performed in inner loop::
    
        STOP
            ID_NAME                = global_stop
            ITER_MAX               = 0
        END_

    - ``OPT_PARAM``: Disable filter::

        OPT_PARAM
            ...
            FILTER_RADIUS = 0
        END_

- ``<job>_RDO.par`` Tosca input file for the outer loop/RDO. The modified DRESPs are defined here, coninciding with the definitions in ``<job>.par``. RDO specific modifications:

    - ``DRIVER`` block: Calls Python script ``run_inner_loop.py``. Make sure to define ``script_directory``: ::

        DRIVER
            ! SET DIRECTORY FOR PYTHON-SCRIPTS/ISIGHT-MODEL
            script_directory = r'/path/to/<script_dir>'
            ! DRIVER TO LAUNCH INNER LOOP VIA PYTHON-SCRIPT
            input_dir = '__WORKDIR__'[:-(len('__JOBNAME__')+1)]
            call_inner_loop = f'"{script_directory}/run_inner_loop.py" -sd "{script_directory}" -id "{input_dir}" -j __FE_MODEL_LIST__'
            driver.registerModuleHook(ToscaModules.FEM_MODIF, HookTypes.PRE, EventTimes.EVER, call_inner_loop)
        END_

    - ``DRESP``: DRESPs for RDO based on output files of inner loop. Important settings are the ``TYPE = SENSITIVITY_ELEMENT`` and ``FIELD_INPUT_FILE = DRESP_[OBJ_FUNC/CON]<OBJ_FUNC/CON_ID>.onf``. Set the ``<OBJ_FUNC/CON_ID>`` in to match the objective function or constraints defined in ``<job>.par`` in all caps and choose ``OBJ_FUNC/CON`` accordingly: ::

        DRESP
            ID_NAME = <DRESP_ID>
            DEF_TYPE = SYSTEM
            EL_GROUP = ALL_ELEMENTS
            TYPE = SENSITIVITY_ELEMENT
            FIELD_INPUT_FILE = DRESP_[OBJ_FUNC/CON]<OBJ_FUNC/CON_ID>.onf
        END_

    - ``OPTIONS``: Call the solver sequentially to make sure that the required files are written for the inner loop: :: 
        
        OPTIONS
            SOLVER_RUN_MODE = SEQUENTIAL
        END_

- ``config_rdo.py``: Copy ``config_rdo_template.py`` from source files and rename. The stochastic properties for the RVs as well as runtime options for the inner loop are defined in this file. Parameters:

    - ``number_of_rv``: Number of RVs
    - ``mean_rv, sigma_rv, delta_rv``: Stochastic properties for RVs. Each property must contain as many list elements as RVs present, the values may be different.
    - ``use_central_differences = True/False``: Use central differences with respect to RVs, default: ``False``
    - ``run_on_windows = True/False``: Switch for execution on windows or linux SYSTEM
    - ``verbose = True/False``:  Toggle additional debug output to ``TOSCA.OUT``, keeping subdirectories in ``inner_loop/.../tosca/run_XXX/<job>`` as well as directories in ``inner_loop/`` for all cycles

- ``isight_model.zmf``: The following components of the Isight model have to be configured for the job:

    .. figure:: ./img/isight.png
        :alt: Workflow of Isight model ``inner_loop.zmf``
        :align: center

        `Fig. 1` Workflow of Isight model ``inner_loop.zmf``


    - ``inner_loop``: Change length of parameter to match number of RVs
    - ``finite_differences``: Parallel execution settings
    - ``define_RV``: OPTIONAL, add any job-specific copy rules for, e.g., pre-generated files to be copied based on the iteration of the inner loop.
    - ``modify_abq``: Add name ``<job>.inp`` under files so that input file is found. **Use the actual name here.** This is required to copy the input file to the subdirectories for the finite difference steps. Optionally, define the RVs within the input file through the component, e.g., writing values for loads, boundary conditions, etc. If you defined, e.g., copy rules in the previous component so that the input file may import a distribution file using a general name, no changes are required here.
    - ``run_tosca_<os>``: Adapt script to copy additional job specific files from <input> to working directory of inner loop iteration and runtime options for the call to ``ToscaStructure``

Execution
---------

The optimization is started via a terminal: ::

    cd <input_dir>
    ToscaStructure -j <job>_RDO.par

.. attention::
    The execution environment when using ``abaqus optimization`` to start an optimization job is different and lead to errors regarding Java Runtime Engine for Isight when tested during development. Therefore, this option is not supported.
