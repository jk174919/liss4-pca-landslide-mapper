from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from sklearn.ensemble import RandomForestClassifier

NODATA_OUT = -9999.0


def _windows(width, height, size=512):
    for row in range(0, height, size):
        for col in range(0, width, size):
            yield Window(col, row, min(size, width-col), min(size, height-row))


def run_pca(image_path, pca_dir, pc4_dir, landslide_dir, labels_path=None,
            normalize=False, candidate_quantile=0.975, max_train_samples=150000):
    image_path = Path(image_path)
    stem = image_path.stem
    out_pca = Path(pca_dir); out_pc4 = Path(pc4_dir); out_slide = Path(landslide_dir)
    for folder in (out_pca, out_pc4, out_slide): folder.mkdir(parents=True, exist_ok=True)
    pca_path = out_pca / f"{stem}_PCA6_components.tif"
    pc4_path = out_pc4 / f"{stem}_PCA_PC4.tif"
    slide_path = out_slide / f"{stem}_PCA_PC4_landslide_candidates.tif"
    prob_path = out_slide / f"{stem}_PCA_landslide_probability.tif"

    with rasterio.open(image_path) as src:
        if src.count != 6:
            raise ValueError(f"Expected exactly 6 bands (3 pre + 3 post), found {src.count}.")
        if src.crs is None:
            raise ValueError("Input raster has no CRS. Georeference it before processing.")
        profile = src.profile.copy()
        width, height = src.width, src.height
        count = 0; total = np.zeros(6, dtype=np.float64); cross = np.zeros((6,6), dtype=np.float64)
        for win in _windows(width,height):
            data = src.read(window=win, out_dtype="float64")
            valid = np.all(np.isfinite(data), axis=0) & np.all(src.read_masks(window=win)>0, axis=0)
            x = data[:,valid].T
            if x.size:
                count += x.shape[0]; total += x.sum(axis=0); cross += x.T @ x
        if count < 2: raise ValueError("Not enough valid pixels to calculate PCA.")
        mean = total/count
        cov = (cross - count*np.outer(mean,mean))/(count-1)
        if normalize:
            scale = np.sqrt(np.maximum(np.diag(cov), 1e-20))
            cov = cov / np.outer(scale,scale)
        vals, vecs = np.linalg.eigh(cov)
        order = np.argsort(vals)[::-1]
        vals = np.maximum(vals[order],0); components = vecs[:,order]
        if vals.sum() <= 1e-20: raise ValueError("All six bands have zero variance; PCA cannot produce components.")
        if normalize: scale = np.sqrt(np.maximum(np.diag((cross-count*np.outer(mean,mean))/(count-1)),1e-20))
        else: scale = np.ones(6)

        out_profile=profile.copy(); out_profile.update(count=6,dtype="float32",nodata=NODATA_OUT,compress="deflate",predictor=3,bigtiff="IF_SAFER")
        pc4_profile=out_profile.copy(); pc4_profile.update(count=1)
        pca_path.parent.mkdir(parents=True,exist_ok=True)
        with rasterio.open(pca_path,"w",**out_profile) as dst, rasterio.open(pc4_path,"w",**pc4_profile) as pc4dst:
            dst.update_tags(AREA_OR_POINT=profile.get("AREA_OR_POINT","Area"), PCA_METHOD="covariance" if not normalize else "correlation", PCA_INPUT_BANDS="pre:1-3;post:4-6", EXPLAINED_VARIANCE=",".join(f"{v/vals.sum():.8f}" for v in vals))
            pc4dst.update_tags(PCA_COMPONENT="PC4", PCA_INPUT_BANDS="pre:1-3;post:4-6")
            pc4_samples=[]; pc4_offset=0
            for win in _windows(width,height):
                data=src.read(window=win,out_dtype="float64")
                valid=np.all(np.isfinite(data),axis=0)&np.all(src.read_masks(window=win)>0,axis=0)
                transformed=np.full((6,int(win.height),int(win.width)),NODATA_OUT,dtype="float32")
                if np.any(valid):
                    x=data[:,valid].T
                    scores=((x-mean)/scale)@components
                    transformed[:,valid]=scores.T.astype("float32")
                    pc4_samples.append(scores[:,3].astype("float32"))
                dst.write(transformed,window=win)
                pc4dst.write(transformed[3:4],window=win)
        pc4_values=np.concatenate(pc4_samples)
        threshold=float(np.quantile(np.abs(pc4_values),candidate_quantile))

        if labels_path:
            with rasterio.open(labels_path) as lab:
                if (lab.width,lab.height)!=(width,height) or lab.transform!=profile["transform"] or lab.crs!=profile["crs"]:
                    raise ValueError("Training labels must match input raster dimensions, transform, and CRS exactly.")
                xs=[]; ys=[]
                for win in _windows(width,height):
                    scores=np.full((6,int(win.height),int(win.width)),np.nan,dtype="float32")
                    # Re-read source pixels and transform in chunks.
                    raw=src.read(window=win,out_dtype="float64")
                    valid=np.all(np.isfinite(raw),axis=0)&np.all(src.read_masks(window=win)>0,axis=0)
                    if not np.any(valid): continue
                    scores[:,valid]=(((raw[:,valid].T-mean)/scale)@components).T
                    y=lab.read(1,window=win)
                    yvalid=valid&(lab.read_masks(1,window=win)>0)&np.isin(y,[0,1])
                    if np.any(yvalid):
                        xs.append(scores[:,yvalid].T); ys.append(y[yvalid].astype("uint8"))
                if not ys: raise ValueError("Training raster has no valid 0/1 samples (0=background, 1=landslide).")
            X=np.concatenate(xs); y=np.concatenate(ys)
            if np.unique(y).size<2: raise ValueError("Training labels must include both 0 (background) and 1 (landslide).")
            rng=np.random.default_rng(42)
            if len(y)>max_train_samples:
                idx=rng.choice(len(y),max_train_samples,replace=False); X=X[idx]; y=y[idx]
            model=RandomForestClassifier(n_estimators=300,max_depth=18,min_samples_leaf=2,class_weight="balanced",n_jobs=-1,random_state=42)
            model.fit(X,y)
            method="Random Forest trained from supplied 0/1 labels"
        else:
            model=None
            # Unsupervised fallback on PC4; this is not a trained landslide classifier.
            method="PC4 absolute-value quantile heuristic (no labels supplied)"

        slide_profile=profile.copy(); slide_profile.update(count=1,dtype="uint8",nodata=255,compress="deflate",bigtiff="IF_SAFER")
        with rasterio.open(slide_path,"w",**slide_profile) as sd:
            sd.update_tags(METHOD=method,THRESHOLD=str(threshold),CLASS_0="not flagged",CLASS_1="possible landslide candidate")
            if labels_path:
                prob_profile=profile.copy(); prob_profile.update(count=1,dtype="float32",nodata=NODATA_OUT,compress="deflate",predictor=3,bigtiff="IF_SAFER")
                pdst=rasterio.open(prob_path,"w",**prob_profile)
                pdst.update_tags(METHOD=method,POSITIVE_CLASS="landslide",PROBABILITY_RANGE="0-1")
            for win in _windows(width,height):
                data=src.read(window=win,out_dtype="float64")
                valid=np.all(np.isfinite(data),axis=0)&np.all(src.read_masks(window=win)>0,axis=0)
                mask=np.full((int(win.height),int(win.width)),255,dtype="uint8")
                if np.any(valid):
                    scores=((data[:,valid].T-mean)/scale)@components
                    if labels_path:
                        probs=model.predict_proba(scores)[:,list(model.classes_).index(1)]
                        mask[valid]=(probs>=0.5).astype("uint8")
                        pb=np.full(mask.shape,NODATA_OUT,dtype="float32"); pb[valid]=probs.astype("float32"); pdst.write(pb,1,window=win)
                    else:
                        mask[valid]=((threshold>0) & (np.abs(scores[:,3])>=threshold)).astype("uint8")
                sd.write(mask,1,window=win)
            if labels_path: pdst.close()
    return {"pca":str(pca_path),"pc4":str(pc4_path),"candidates":str(slide_path),"probability":str(prob_path) if labels_path else None,"method":method,"variance":(vals/vals.sum()).tolist(),"threshold":threshold}


