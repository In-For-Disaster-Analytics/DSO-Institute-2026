# Tutorial Notes for Students

These notes accompany the Day 3 tutorials. They are intended to help you understand what to expect before you begin the notebooks and what ideas you should be able to explain after working through them.

Day 3 focuses on building publishable interactive geospatial products. In the morning, you will use CKAN-backed compaction data to build interactive Plotly charts and a Folium map, prepare those visualization products for publication back into CKAN, and discuss how WebODM can use LS6 to distribute heavier geospatial computation. In the afternoon, you will work through remote-sensing data capture processes for surface displacement and vertical land motion.

## What You Should Learn

By the end of the Day 3 tutorials, you should understand the following concepts:

- CKAN can be used as a source for station datasets and measurement resources
- compaction measurements often need to be rebuilt, standardized, and combined before mapping
- cleaned site metadata and long-form time-series data are reusable data products
- Plotly can be used to create interactive site-level time-series charts
- Folium maps can combine spatial layers, station markers, and popup visualizations into one publishable map
- generated HTML charts and maps can be uploaded to CKAN as reusable visualization resources
- WebODM provides a web interface for imagery and mapping workflows
- LS6 can be used to distribute compute-heavy processing behind user-facing geospatial tools
- OPERA DISP-S1 data can be searched, selected, downloaded, and inspected for a chosen area and time range
- vertical land motion data can be captured for a study area by clipping, converting, interpolating, and mapping

The main idea is that Day 3 moves from CKAN-hosted data to interactive visualization products, then back into CKAN for publishing and reuse.

## Morning Workflow: Interactive Publishing With CKAN And WebODM

The morning session has two connected parts. The notebooks build a workflow from CKAN-backed station resources to interactive Plotly charts and a publishable Folium map. The discussion also introduces WebODM, where large aerial imagery processing jobs can leverage our HPC systems to generate 3D Models and orthophotos.

What to learn:

- how the WebODM dashboard supports user-facing imagery and mapping workflows
- how the WebODM codebase connects a web application to backend processing
- how sensor datasets are discovered from CKAN
- how site names and dates are standardized
- how cleaned CSV files become stable products that can be registered
- how popup charts and Folium maps are created from those cleaned products
- how generated HTML charts and maps are uploaded back into CKAN
- how CKAN web views can make interactive outputs available through the catalog


What to notice while working:

- which files are inputs and which files are generated outputs
- whether site names match consistently between metadata and measurement files
- whether dates are converted into usable datetime values
- where the workflow uses data from CKAN and where it publishes new products into CKAN
- how generated HTML files become CKAN resources
- how the same cleaned data supports both interactive visualization and catalog publication
- which parts of a workflow belong in a notebook, a catalog, a web dashboard, or a distributed computing system

## Morning Discussion: WebODM And Distributed Processing

This morning discussion will introduce the TACC WebODM deployment and the related code repository:

- [TACC WebODM Dashboard](https://webodm.tacc.utexas.edu/dashboard/)


What to learn:

- WebODM provides a browser-based interface for imagery processing and map-product workflows
- some geospatial products are too computationally expensive to generate comfortably in a local notebook
- LS6 is used as the distributed computing backend for larger processing jobs




## Notebook 1: Compaction Data Ingest

[`Morning/1_compaction_data_ingest.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-3/Morning/1_compaction_data_ingest.ipynb) focuses on rebuilding compaction inputs from CKAN and Upstream resources.

Before you start:

- make sure the notebook can reach the CKAN catalog
- know that this notebook rebuilds local CSV inputs from registered station resources
- run it before the combine and mapping notebooks if you need fresh station CSV files

Expected outputs:

- the `csv_files/` directory contains rebuilt per-station compaction CSV files
- `csv_files/TABLE1_CompactionSites.csv` is rebuilt from station metadata
- the notebook previews the discovered station datasets and confirms the generated files

As you work through it, pay attention to how the notebook:

- queries CKAN for Houston-area extensometer campaign station datasets
- identifies the measurement resource URL for each station
- creates the `csv_files/` output directory
- fetches measurement resources and rebuilds per-station CSV files
- rebuilds `TABLE1_CompactionSites.csv` from station metadata
- confirms that the expected files were written

The main lesson is that the workflow can start from registered catalog resources instead of relying on manual downloads.

## Notebook 2: Combine Site Data

[`Morning/2_combine_site_data.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-3/Morning/2_combine_site_data.ipynb) focuses on cleaning and combining station data.

Before you start:

- run the compaction ingest notebook first, or confirm that the expected files already exist in `csv_files/`
- review the station metadata and measurement filenames as inputs to the cleaning workflow
- be ready to register cleaned CSV products in CKAN when the notebook reaches that checkpoint

Expected outputs:

- `compaction_sites.csv` contains cleaned station metadata for map markers
- `combined_site_data.csv` contains the long-form compaction time series
- the cleaned CSV products are ready to register as reusable CKAN resources

As you work through it, pay attention to how the notebook:

- loads the generated station CSV files and metadata table
- builds a simplified site-name field for matching
- saves cleaned site metadata as `compaction_sites.csv`
- checks measurement filenames against known site names
- handles special site-name cases
- concatenates individual station histories into `combined_site_data.csv`
- explains why this is a good point to register cleaned data in CKAN

The main lesson is that cleaned, documented intermediate products are valuable because later notebooks and users can reuse them.

## Notebook 3: Folium Mapping

[`Morning/3_folium_mapping.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-3/Morning/3_folium_mapping.ipynb) focuses on creating interactive Plotly popups, assembling a Folium map, and publishing the generated HTML products into CKAN.

Before you start:

- make sure `compaction_sites.csv` and `combined_site_data.csv` are available from the previous notebook
- confirm that the spatial boundary data and Python mapping libraries are available
- have CKAN credentials ready if you will publish popup HTML files and the final map

Expected outputs:

- one interactive popup HTML chart is generated for each compaction site
- a Folium map combines base layers, county outlines, site markers, and popup charts
- generated HTML files and the final map are uploaded to CKAN, with a web view created for the map

As you work through it, pay attention to how the notebook:

- loads county boundaries, site metadata, and compaction measurements
- cleans date fields for plotting
- builds a preview Plotly chart for one site
- wraps the chart logic in a reusable function
- generates one popup HTML chart per site
- uploads popup files to CKAN
- assembles a Folium map with base layers, markers, popups, and county outlines
- uploads the final map and creates a CKAN web view

The main lesson is that interactive plots and maps become more useful when they are prepared as shareable HTML resources and published through CKAN.

## Afternoon Workflow: Remote-Sensing Data Capture

The afternoon notebooks introduce remote-sensing workflows for capturing surface movement data.

What to learn:

- remote-sensing products usually require authentication, spatial selection, and careful download choices
- bounding boxes and time ranges directly affect what data is captured and how much storage is needed
- displacement and velocity products answer different questions
- static datasets such as global VLM can be clipped and interpolated for a local study area
- interactive maps are useful for both selecting an area and reviewing results
- captured remote-sensing data often needs to be converted into local files before analysis or mapping

## OPERA Surface Displacement Notebook

[`Afternoon/OPERA Surface Displacement.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-3/Afternoon/OPERA%20Surface%20Displacement.ipynb) focuses on capturing OPERA DISP-S1 products for a selected study area and time range.

As you work through it, pay attention to how the notebook:

- prepares the analysis environment
- authenticates with NASA Earthdata and Alaska Satellite Facility access
- lets you draw or define a location of interest
- sets a time range for DISP-S1 products
- estimates download size before downloading
- downloads selected surface displacement data
- opens and visualizes a downloaded dataset

The main lesson is that satellite data capture requires careful choices about location, time period, credentials, and storage before analysis begins.

## Vertical Land Motion Notebook

[`Afternoon/VLM data download_updated.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-3/Afternoon/VLM%20data%20download_updated.ipynb) focuses on capturing a local vertical land motion product from a global dataset.

As you work through it, pay attention to how the notebook:

- downloads the global VLM source file
- lets you draw a bounding box on a map
- clips the global data to that bounding box
- converts the filtered text data to CSV
- interpolates point values with inverse distance weighting
- exports a GeoTIFF
- visualizes the result on an interactive map

The main lesson is that large geospatial products often need to be captured, reduced, and converted for a local study area before they are useful for analysis or mapping.

## Recommended Order Of Study

To get the most from Day 3, use the following order:

1. Run the compaction ingest notebook and confirm that CKAN-backed station files are created.
2. Run the combine-site-data notebook and inspect `compaction_sites.csv` and `combined_site_data.csv`.
3. Register the cleaned CSV products when prompted so the source data is discoverable.
4. Run the Folium mapping notebook and verify the popup charts before generating the full map.
5. Publish the generated popup HTML files and final map back into CKAN.
6. Work through the OPERA DISP-S1 notebook and focus on authentication, bounding boxes, dates, and download size.
7. Work through the VLM notebook and focus on clipping, CSV conversion, interpolation, and map review.

## Main Takeaway

The most important idea to retain is that Day 3 connects data systems, interactive visualization, publishing, and remote-sensing data capture:

- CKAN and Upstream provide discoverable data resources
- cleaning and standardization create reusable products
- Plotly and Folium turn those products into interactive charts and maps
- CKAN can publish generated HTML visualizations as reusable resources and web views
- OPERA and VLM workflows show how to capture remote-sensing data for later analysis
