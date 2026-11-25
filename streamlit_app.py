from pathlib import Path
import tempfile
import streamlit as st
from pca_landslide import run_pca

st.set_page_config(page_title="LISS-4 PCA & Landslide Mapper", page_icon="🛰️", layout="wide")
st.title("LISS-4 Change PCA and Landslide Candidates")
st.markdown("Upload a six-band raster: bands 1–3 are pre-event and bands 4–6 are post-event. The output rasters preserve the source CRS, transform, and NoData mask.")
st.info("PC4 alone cannot confirm a landslide. Add a co-registered training raster (0=background, 1=landslide) to train Random Forest. Without labels, the app marks extreme absolute PC4 values as exploratory candidates.")

image=st.file_uploader("Six-band input raster (GeoTIFF)",type=["tif","tiff"])
labels=st.file_uploader("Optional training labels raster (same grid; 0=background, 1=landslide)",type=["tif","tiff"])
a,b,c=st.columns(3)
with a: pca_dir=st.text_input("Folder for six PCA bands",value="PCA_Output")
with b: pc4_dir=st.text_input("Folder for PC4 raster",value="PC4_Output")
with c: landslide_dir=st.text_input("Folder for landslide candidates",value="Landslide_Output")
normalize=st.checkbox("Normalize bands to unit variance before PCA",value=False,help="Off uses covariance PCA, appropriate when all six bands share the same reflectance units.")
quantile=st.slider("PC4 outlier quantile (used only without labels)",0.90,0.999,0.975,0.001)

if st.button("Run PCA and map candidates",type="primary",disabled=image is None):
    try:
        with tempfile.TemporaryDirectory(prefix="liss4_pca_") as tmp:
            tmp=Path(tmp)
            source=tmp / image.name
            source.write_bytes(image.getbuffer())
            label_path=None
            if labels is not None:
                label_path=tmp / labels.name
                label_path.write_bytes(labels.getbuffer())
            with st.spinner("Calculating PCA and candidate map. Large rasters may take several minutes…"):
                result=run_pca(source,pca_dir,pc4_dir,landslide_dir,label_path,normalize,float(quantile))
        st.success("Processing finished.")
        st.write("**Method:**",result["method"])
        st.write("**Explained variance by PC:**",[round(v,4) for v in result["variance"]])
        st.write("**PC4 candidate threshold (absolute score):**",round(result["threshold"],5))
        st.write("**Outputs**")
        st.code("\n".join(f"{k}: {v}" for k,v in result.items() if k in ("pca","pc4","candidates","probability") and v))
    except Exception as exc:
        st.error(str(exc))

st.caption("The unlabelled PC4 result is a screening layer, not a validated landslide inventory. Verify candidates against imagery, field data, and expert interpretation.")

