# LISS-4 Six-Band PCA and Landslide Candidate Mapper

A local Streamlit app for a six-band raster where bands 1–3 are pre-event and 4–6 are post-event.

## Run on Windows

Install Python 3.10 or newer. Double-click `Install_and_Run_LISS4_PCA.bat`; it installs the requirements and opens Streamlit in your browser. Or run `py -3 -m pip install -r requirements.txt` followed by `py -3 -m streamlit run streamlit_app.py`.

Upload a six-band GeoTIFF (`.tif`/`.tiff`) or ERDAS Imagine raster (`.img`) and enter three separate output folders or use each **Browse** button to choose folders on the local computer running Streamlit. Surrounding quotes in manually entered paths are ignored. If the IMG uses an external `.ige` data file, upload the matching `.img` and `.ige` together with identical base names. If reading fails, first confirm the image opens in QGIS and contains six readable bands. The six-band Float32 PCA raster, standalone PC4, and landslide candidate raster are saved separately and named from the input filename with PCA labels.

## PCA and landslide method

PCA is calculated across valid pixels from all six bands. By default it uses covariance PCA (all bands are assumed to use the same reflectance units); optional unit-variance normalization uses correlation PCA. PC scores and the explained-variance fractions are reported. Outputs retain the source grid and CRS.

For a supervised landslide probability map, upload a co-registered label raster with 0 for background and 1 for landslide. A Random Forest uses all six PC scores and outputs a probability raster plus a 0/1 candidate map. Without labels, an Isolation Forest on PC1–PC4 supports a PC4-primary quantile screen. Extreme PC1 and PC3 responses are suppressed as possible snow and hydrothermal-mineral confounders, following the supplied interpretation figure. This remains an exploratory anomaly layer, not a trained or validated landslide prediction.

## Requirements and limits

Input must have exactly six bands and a CRS. Labels, if supplied, must match the input grid exactly. Landslide mapping quality depends on representative labels and independent validation. PC4 is the primary unlabelled signal; the interpretation figure's PC2 steep-slope cue can support review, but no DEM-derived slope is available unless provided separately. The app does not establish landslide truth from PCA alone.






