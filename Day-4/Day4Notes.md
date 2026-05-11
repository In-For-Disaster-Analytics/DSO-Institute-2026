# Tutorial Notes for Students

These notes accompany the Day 4 tutorials. They are intended to help you understand what to expect before you begin the notebooks and what ideas you should be able to explain after working through them.

Day 4 focuses on groundwater model execution and subsidence analysis. In the morning, you will use FloPy to load, run, and inspect MODFLOW models. In the afternoon, you will analyze OPERA DISP-S1 satellite products to estimate displacement and velocity.

## What You Should Learn

By the end of the Day 4 tutorials, you should understand the following concepts:

- FloPy provides a Python interface for building, loading, running, and inspecting MODFLOW models
- model workspaces should separate source inputs from generated outputs
- MODFLOW runs should be checked for success before interpreting results
- head files and budget files are core outputs for groundwater model interpretation
- map-based model plots can show grids, boundaries, elevations, heads, and flow vectors
- OPERA DISP-S1 data can be processed into cumulative displacement and velocity products
- InSAR displacement is relative and requires a stable reference point

The main idea is that computational notebooks can make model execution, output checking, and visualization more transparent and repeatable.

## Morning Workflow: FloPy And MODFLOW

The morning notebooks introduce FloPy through a small example and then apply the same logic to existing MODFLOW model files.

What to learn:

- how FloPy represents a simulation as Python objects
- how model directories and output workspaces are configured
- how existing model input files are loaded
- how a model run is written and executed
- how expected output files are checked
- how simulated heads and budget terms are visualized

What to notice while working:

- which cells define paths and executables
- which files are original model inputs and which are generated outputs
- whether the model run returns a success flag
- whether head and cell-budget files are present before plotting
- how changing an input package would affect the interpretation of later plots

## FloPy Intro Example

[`Morning/flopy_example.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-4/Morning/flopy_example.ipynb) is a compact introduction to building a small MODFLOW 6 simulation in Python.

Before you start:

- make sure FloPy is available in the notebook environment
- no external model files are required for the basic example
- treat this notebook as a structural introduction before running larger existing models

Expected outputs:

- a small MODFLOW 6 simulation is assembled as Python objects
- grid, solver, boundary, and output-control packages are visible in the notebook
- head and budget output names are configured so the example can be extended to a model run

As you work through it, pay attention to how the notebook:

- imports FloPy and creates a temporary workspace
- creates an `MFSimulation` container
- defines stress periods, a solver, and a groundwater flow model
- defines grid, starting-head, and flow-property packages
- adds constant-head boundaries
- configures output control for head and budget files

The main lesson is that FloPy exposes the model structure directly in Python before you move to larger existing models.

## MODFLOW Model Run Notebooks

The morning folder includes several focused model-run notebooks:

- [`Morning/Run_MODFLOW6_TACC.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-4/Morning/Run_MODFLOW6_TACC.ipynb)
- [`Morning/Run_MODFLOW_2000_TACC.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-4/Morning/Run_MODFLOW_2000_TACC.ipynb)
- [`Morning/Run_MODFLOW_96_TACC.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-4/Morning/Run_MODFLOW_96_TACC.ipynb)
- [`Morning/Run_MODFLOW_USG_TACC.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-4/Morning/Run_MODFLOW_USG_TACC.ipynb)

These notebooks focus on local FloPy workflows rather than Tapis job submission.

Before you start:

- make sure the required model input files are available from shared storage or the configured CKAN source
- confirm that the appropriate MODFLOW executable is available for the model version
- review the path and workspace cells before running the model

Expected outputs:

- a local tutorial run workspace is created under `model_output_directory/`
- model input files are staged, loaded, or written as appropriate for the MODFLOW version
- run messages and expected output files are checked before any interpretation step

As you work through them, pay attention to how each notebook:

- locates an existing model from shared model storage
- stages or points the model to a tutorial output workspace
- loads the model for inspection with FloPy when appropriate
- runs the model input files
- checks that expected output files were produced

The main lesson is that different MODFLOW versions may require different handling, but the basic workflow remains similar: locate inputs, configure a workspace, run the model, and verify outputs.

## Gulf Model Notebook

[`Morning/Run_GULF_v4_TACC.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-4/Morning/Run_GULF_v4_TACC.ipynb) demonstrates a fuller MODFLOW 6 workflow using a Gulf Coast aquifer model.

Before you start:

- make sure the Gulf model input files and MODFLOW 6 executable are available
- check the source model directory, output workspace, and executable settings before running
- expect the model run and plotting cells to take longer than the small FloPy example

Expected outputs:

- the Gulf model simulation is loaded, redirected to a separate output workspace, written, and run
- key binary outputs such as head and cell-budget files are confirmed
- maps and plots show model structure, bottom elevation, heads, contours, and specific discharge vectors

As you work through it, pay attention to how the notebook:

- downloads or locates the MODFLOW 6 executable
- loads the Python and FloPy tools used for modeling
- sets source model paths, output workspaces, and executable names
- loads an existing simulation from model input files
- redirects output to a separate workspace
- writes and runs the model
- checks for head and cell-budget files
- plots boundary conditions, bottom elevation, heads, contours, and specific discharge vectors

The main lesson is that running a model is only part of the workflow. You must also check outputs and inspect results before drawing conclusions.

## Afternoon Workflow: OPERA Subsidence Analysis

The afternoon notebook uses OPERA DISP-S1 products to estimate surface movement over a selected study area.

What to learn:

- how to select a study area with an interactive map
- how frame IDs, bounding boxes, and dates define the download request
- how NASA Earthdata credentials are used for data access
- how downloaded files are combined into a time series
- why a stable reference point is needed for relative displacement data
- how cumulative displacement and velocity products are generated

What to notice while working:

- whether the selected frame and bounding box match the intended study area
- whether the selected time range is reasonable for the analysis question
- how many files and time steps are included
- which reference point is selected
- how displacement maps differ from velocity maps

## OPERA DISP-S1 Subsidence Notebook

[`Afternoon/Opera- Subsidence.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-4/Afternoon/Opera-%20Subsidence.ipynb) focuses on downloading and analyzing satellite radar data for subsidence or uplift.

As you work through it, pay attention to how the notebook:

- installs and loads required packages
- lets you draw a study area and choose an available satellite frame
- asks you to copy confirmed parameters into the next cell
- authenticates with NASA Earthdata
- downloads data for the selected area and time range
- previews downloaded files
- combines files into a time series
- selects candidate stable reference points
- creates cumulative displacement maps
- generates GeoTIFF output
- creates velocity maps in millimeters per year

The main lesson is that InSAR products require careful setup and interpretation because the measured movement is relative to a reference location.

## Recommended Order Of Study

To get the most from Day 4, use the following order:

1. Run the FloPy intro notebook and focus on how a model is represented in Python.
2. Run one of the focused MODFLOW notebooks and identify the path, workspace, run, and output-check steps.
3. Run the Gulf model notebook and inspect both the model-run messages and the resulting plots.
4. Compare head arrays, contours, boundary conditions, and specific discharge vectors.
5. Run the OPERA subsidence notebook from top to bottom without skipping cells.
6. Review the displacement and velocity maps, and explain the role of the reference point.

## Main Takeaway

The most important idea to retain is that Day 4 emphasizes repeatable computational analysis:

- FloPy makes groundwater model setup, execution, and inspection available from Python
- output checks are necessary before interpretation
- model plots help connect files and numerical outputs to physical meaning
- OPERA DISP-S1 products provide an independent satellite-based view of surface movement
