"""Offline document processing; explicit media references only, run on worker thread."""
def process(image_bytes, corners=None, grayscale=True, rotation=0):
    import cv2
    import numpy as np
    if rotation not in (0,90,180,270):raise ValueError('Rotation must be a right angle')
    img=cv2.imdecode(np.frombuffer(image_bytes,dtype=np.uint8),cv2.IMREAD_COLOR)
    if img is None:raise ValueError('Invalid image')
    h,w=img.shape[:2]
    if w*h>24_000_000:raise ValueError('Document too large')
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    detected=False
    if corners is None:
        contours,_=cv2.findContours(cv2.Canny(cv2.GaussianBlur(gray,(5,5),0),60,180),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in sorted(contours,key=cv2.contourArea,reverse=True)[:10]:
            poly=cv2.approxPolyDP(contour,.02*cv2.arcLength(contour,True),True)
            if len(poly)==4 and cv2.isContourConvex(poly) and cv2.contourArea(poly)>.15*w*h:
                corners=poly.reshape(4,2);detected=True;break
    if corners is not None:
        pts=np.asarray(corners,dtype=np.float32)
        if pts.shape!=(4,2) or not np.isfinite(pts).all() or (pts<0).any() or (pts[:,0]>=w).any() or (pts[:,1]>=h).any():raise ValueError('Invalid document corners')
        # Cyclic ordering then top-left origin avoids duplicate min/max-sum points.
        center=pts.mean(axis=0);pts=pts[np.argsort(np.arctan2(pts[:,1]-center[1],pts[:,0]-center[0]))]
        pts=np.roll(pts,-np.argmin(pts.sum(axis=1)),axis=0)
        outw=int(max(np.linalg.norm(pts[1]-pts[0]),np.linalg.norm(pts[2]-pts[3])))
        outh=int(max(np.linalg.norm(pts[3]-pts[0]),np.linalg.norm(pts[2]-pts[1])))
        if min(outw,outh)<32 or outw*outh>24_000_000:raise ValueError('Degenerate document')
        matrix=cv2.getPerspectiveTransform(pts,np.float32([[0,0],[outw-1,0],[outw-1,outh-1],[0,outh-1]]))
        img=cv2.warpPerspective(img,matrix,(outw,outh))
    if grayscale:img=cv2.createCLAHE(2.0,(8,8)).apply(cv2.cvtColor(img,cv2.COLOR_BGR2GRAY))
    if rotation:img=np.rot90(img,-rotation//90).copy()
    ok,data=cv2.imencode('.png',img)
    if not ok:raise ValueError('Document encoding failed')
    return data.tobytes(),dict(width=img.shape[1],height=img.shape[0],edgesDetected=detected)

def export_pdf(pages, target):
    import io
    from PIL import Image
    if not 1<=len(pages)<=20:raise ValueError('Use 1 to 20 pages')
    images=[]
    try:
        for data in pages:images.append(Image.open(io.BytesIO(data)).convert('RGB'))
        images[0].save(target,'PDF',save_all=True,append_images=images[1:],resolution=150)
    finally:
        for img in images:img.close()
