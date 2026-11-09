def feature_frame(features):
    require(set(features)==set(FEATURE_NAMES),'Feature schema differs')
    frame=pd.DataFrame([[float(features[n]) for n in FEATURE_NAMES]],columns=list(FEATURE_NAMES))
    require(np.isfinite(frame.to_numpy()).all(),'Non-finite features');return frame
