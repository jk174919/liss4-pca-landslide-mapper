from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog
import streamlit as st
from pca_landslide import run_pca

RASTER_EXTS={".tif",".tiff",".img"}


def save_raster_uploads(files, folder):
    folder.mkdir(parents=True,exist_ok=True)
    raster_paths=[]
    for uploaded in files or []:
        path=folder / Path(uploaded.name).name
        path.write_bytes(uploaded.getbuffer())
        if path.suffix.lower() in RASTER_EXTS:
            raster_paths.append(path)
    if len(raster_paths)!=1:
        raise ValueError("Upload exactly one raster image. For IMG files with an external .ige sidecar, select both the .img and .ige files together.")
    return raster_paths[0]


def browse_folder(key):
    root=tk.Tk()
    root.withdraw()
    root.attributes("-topmost",True)
    try:
        folder=filedialog.askdirectory(title="Choose output folder",mustexist=False)
    finally:
        root.destroy()
    if folder:
        st.session_state[key]=folder


def clean_folder(value):
    return Path(value.strip().strip('"').strip()).expanduser()


st.set_page_config(page_title="LISS-4 PCA & Landslide Mapper", page_icon="🛰️", layout="wide")
st.title("LISS-4 Change PCA and Landslide Candidates")
st.markdown("Upload a six-band raster: bands 1–3 are pre-event and bands 4–6 are post-event. GeoTIFF (.tif/.tiff) and ERDAS Imagine (.img) are supported. Outputs preserve the source CRS, transform, and NoData mask.")
st.info("PC4 is the primary unlabelled landslide signal. A co-registered training raster (0=background, 1=landslide) enables supervised Random Forest. Without labels, the app uses interpretation-guided Isolation Forest screening; candidates still need validation.")

image_files=st.file_uploader("Six-band input raster (.tif, .tiff, or .img)",type=["tif","tiff","img","ige"],accept_multiple_files=True)
st.caption("For an IMG that uses an external .ige data sidecar, upload the .img and matching .ige together.")
label_files=st.file_uploader("Optional training labels raster (.tif, .tiff, or .img; 0=background, 1=landslide)",type=["tif","tiff","img","ige"],accept_multiple_files=True)
a,b,c=st.columns(3)
with a:
    field,button=st.columns([5,1])
    with field: pca_dir=st.text_input("Folder for six PCA bands",value="PCA_Output",key="pca_dir")
    with button:
        st.write("")
        st.button("Browse",key="browse_pca",on_click=browse_folder,args=("pca_dir",))
with b:
    field,button=st.columns([5,1])
    with field: pc4_dir=st.text_input("Folder for PC4 raster",value="PC4_Output",key="pc4_dir")
    with button:
        st.write("")
        st.button("Browse",key="browse_pc4",on_click=browse_folder,args=("pc4_dir",))
with c:
    field,button=st.columns([5,1])
    with field: landslide_dir=st.text_input("Folder for landslide candidates",value="Landslide_Output",key="landslide_dir")
    with button:
        st.write("")
        st.button("Browse",key="browse_landslide",on_click=browse_folder,args=("landslide_dir",))
normalize=st.checkbox("Normalize bands to unit variance before PCA",value=False,help="Off uses covariance PCA, appropriate when all six bands share the same reflectance units.")
quantile=st.slider("PC4 anomaly quantile (used only without labels)",0.90,0.999,0.975,0.001)

if st.button("Run PCA and map candidates",type="primary",disabled=not image_files):
    try:
        output_dirs=[clean_folder(v) for v in (pca_dir,pc4_dir,landslide_dir)]
        if any(not str(folder) for folder in output_dirs):
            raise ValueError("Choose all three output folders.")
        for folder in output_dirs: folder.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="liss4_pca_") as tmp:
            tmp=Path(tmp)
            source=save_raster_uploads(image_files,tmp/"input")
            label_path=save_raster_uploads(label_files,tmp/"labels") if label_files else None
            with st.spinner("Calculating PCA and candidate map. Large rasters may take several minutes…"):
                result=run_pca(source,*output_dirs,label_path,normalize,float(quantile))
        st.success("Processing finished.")
        st.write("**Method:**",result["method"])
        st.write("**Explained variance by PC:**",[round(v,4) for v in result["variance"]])
        st.write("**PC4 candidate threshold (robust z-score):**",round(result["threshold"],5))
        st.write("**Outputs**")
        st.code("\n".join(f"{k}: {v}" for k,v in result.items() if k in ("pca","pc4","candidates","probability") and v))
    except Exception as exc:
        st.error(f"Raster processing failed: {exc}")
        if image_files and any(Path(f.name).suffix.lower()==".img" for f in image_files):
            st.warning("For ERDAS IMG data, upload the matching .ige sidecar in the same selection if one exists. Keep the .img and .ige base names identical. Also confirm the IMG opens in QGIS and contains exactly six readable bands.")
        with st.expander("Technical details"):
            st.exception(exc)

st.caption("PC4-primary candidate screening is exploratory, not a validated landslide inventory. PC1 and PC3 extremes are suppressed as potential snow/mineral confounders based on the supplied interpretation. Verify candidates against imagery, field data, and expert interpretation.")


