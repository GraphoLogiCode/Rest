import { useEffect, useRef, useState, type PointerEvent } from 'react';
import { createIllustration, getIllustration, deleteIllustration, releaseIllustrationImage, cloudEnabled, type Box, type IllustrationJob } from '../services/illustration';
import './face-editor.css';
import { PreviewInputs } from './PreviewInputs';
import { CloudSignIn } from './CloudSignIn';
import { supabase } from '../services/cloudSession';
import { PreviewProductPicker, PreviewProductCard, type PreviewProduct } from './PreviewProduct';
type Photo = {file: File; url: string; width: number; height: number};
export function FaceEditor() {
  if (import.meta.env.VITE_PHONE_PREVIEW === 'true' && import.meta.env.VITE_PHONE_MODEL_ENABLED !== 'true') {
    return <section className="panel" style={{padding: 24}}>
      <h2>AI preview</h2>
      <p>AI image generation is not available in this phone test. You can explore the app and save check-ins on this device while the model service is being prepared.</p>
    </section>;
  }
  return <FaceEditorWorkspace />;
}
function FaceEditorWorkspace() {
  const [photo, setPhoto] = useState<Photo | null>(null);
  const [face, setFace] = useState<Box>([0,0,64,64]);
  const [edit, setEdit] = useState<Box>([0,0,32,32]);
  const [selection, setSelection] = useState<'face'|'edit'>('face');
  const [consent, setConsent] = useState(false);
  const [product, setProduct] = useState<PreviewProduct | null>(null);
  const [previewProduct, setPreviewProduct] = useState<PreviewProduct | null>(null);
  const [finish, setFinish] = useState('original');
  const [strength, setStrength] = useState('0.15');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [job, setJob] = useState<IllustrationJob | null>(null);
  const current = useRef<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const alive = useRef(true);
  const drag = useRef<[number,number] | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); if (current.current) void deleteIllustration(current.current).catch(()=>{}); }; }, []);
  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);
  useEffect(() => {
    if (!supabase) return;
    let priorUser: string | null | undefined;
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      const nextUser = session?.user.id || null;
      if (priorUser !== undefined && nextUser !== priorUser) {
        controller.current?.abort();
        if (current.current) releaseIllustrationImage(current.current);
        current.current = null; setJob(null); setPhoto(null); setConsent(false); setBusy(false);
      }
      priorUser = nextUser;
    });
    return () => data.subscription.unsubscribe();
  }, []);
  async function clear() {
    controller.current?.abort();
    if (current.current) await deleteIllustration(current.current);
    current.current = null; setJob(null); setBusy(false); setPreviewProduct(null);
  }
  async function upload(file?: File) {
    if (!file) return;
    setError('');
    let url = '';
    try {
      await clear();
      if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 10*1024*1024) throw new Error('Choose a JPG, PNG or WebP under 10 MB.');
      url = URL.createObjectURL(file);
      const image = new Image(); image.src = url; await image.decode();
      const scale = Math.min(1, 1024/Math.max(image.naturalWidth,image.naturalHeight));
      const canvas = document.createElement('canvas'); canvas.width = Math.round(image.naturalWidth*scale); canvas.height = Math.round(image.naturalHeight*scale);
      if (Math.min(canvas.width, canvas.height)<64) throw new Error('Choose a larger photo.');
      canvas.getContext('2d')!.drawImage(image,0,0,canvas.width,canvas.height);
      const blob = await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(new Error('Could not prepare photo.')), 'image/png'));
      if (!alive.current) return;
      const side = Math.max(64,Math.floor(Math.min(canvas.width,canvas.height)*0.65)), left = Math.floor((canvas.width-side)/2), top = Math.floor((canvas.height-side)/2);
      const box: Box = [left,top,left+side,top+side];
      setFace(box); setEdit([left+Math.round(side*.2),top+Math.round(side*.5),left+Math.round(side*.4),top+Math.round(side*.7)]);
      setPhoto({file:new File([blob],'reference.png',{type:'image/png'}),url:URL.createObjectURL(blob),width:canvas.width,height:canvas.height}); setConsent(false);
    } catch(e) { setError(e instanceof Error ? e.message : 'Could not load photo.'); }
    finally { if(url) URL.revokeObjectURL(url); }
  }
  function point(event: PointerEvent<SVGSVGElement>): [number,number] {
    const rect = event.currentTarget.getBoundingClientRect();
    return [Math.round(Math.max(0,Math.min(photo!.width,(event.clientX-rect.left)/rect.width*photo!.width))),Math.round(Math.max(0,Math.min(photo!.height,(event.clientY-rect.top)/rect.height*photo!.height)))];
  }
  function move(event: PointerEvent<SVGSVGElement>) {
    if (!drag.current || busy || job || !photo) return;
    const [x,y] = point(event), [a,b] = drag.current;
    if (selection==='face') {
      const side = Math.min(Math.max(64,Math.abs(x-a),Math.abs(y-b)),photo.width,photo.height);
      const left = Math.min(Math.min(x,a),photo.width-side), top = Math.min(Math.min(y,b),photo.height-side);
      setFace([left,top,left+side,top+side]);
      setEdit([left+Math.round(side*.2),top+Math.round(side*.5),left+Math.round(side*.4),top+Math.round(side*.7)]);
    } else {
      const left=Math.max(face[0],Math.min(x,a)),top=Math.max(face[1],Math.min(y,b));
      const right=Math.min(face[2],Math.max(x,a)),bottom=Math.min(face[3],Math.max(y,b));
      if(right>left && bottom>top) setEdit([left,top,right,bottom]);
    }
    setConsent(false);
  }
  async function generate() {
    if (!photo || !consent || busy) return;
    setBusy(true); setError(''); setPreviewProduct(product);
    const ctrl = new AbortController(); controller.current = ctrl;
    const timeout = window.setTimeout(()=>ctrl.abort(),5*60*1000);
    try {
      let next = await createIllustration(photo.file,{faceBox:face,editBox:edit,strength,finish,product:product ? `${product.brand} · ${product.name}` : ''},ctrl.signal);
      current.current=next.id;
      if (!alive.current || ctrl.signal.aborted) { await deleteIllustration(next.id); return; }
      setJob(next);
      while (next.status==='queued'||next.status==='running') {
        await new Promise(resolve=>setTimeout(resolve,1000));
        next=await getIllustration(next.id,ctrl.signal);
        if(alive.current) setJob(next);
      }
      if(next.status==='failed') throw new Error(next.error || 'Preview failed.');
    } catch(e) {
      if(ctrl.signal.aborted && current.current) await deleteIllustration(current.current).catch(()=>{});
      if(alive.current) setError(ctrl.signal.aborted?'Preview cancelled or timed out.':e instanceof Error?e.message:'Preview failed.');
    } finally { clearTimeout(timeout); if(alive.current) setBusy(false); }
  }
  return <section className="panel face-editor">
    <h2>Your face, a small visual change.</h2>
    {cloudEnabled && <CloudSignIn />}
    <p>Upload a photo, frame your face, then select a small skin area to edit.</p>
    <p className="notice"><strong>AI illustration—not a product result.</strong> This preview cannot show what a product will do to your skin. Use two real dated photos in My photo comparison to record actual progress.</p>
    <PreviewInputs />
    <PreviewProductPicker value={product} onChange={setProduct} disabled={busy || Boolean(job)} />
    {error && <p className="notice error" role="alert">{error}</p>}
    <label className="field">Reference photo (JPG, PNG or WebP, up to 10 MB)<input aria-label="Upload preview photo" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={e=>{void upload(e.target.files?.[0]);e.target.value='';}} /></label>
    {photo && <>
      {!job && <><div className="face-tools"><button className="button secondary" aria-pressed={selection==='face'} onClick={()=>setSelection('face')}>1. Frame your face</button><button className="button secondary" aria-pressed={selection==='edit'} onClick={()=>setSelection('edit')}>2. Select edit area</button></div><p className="small-text">Drag a square around your face, then draw an oval over skin. Keep eyes, lips and hair outside the oval. Selection is manual; the app does not detect faces.</p></>}
      <div className="face-results">
        <figure><figcaption>Original {job?'':'· square: face / shaded oval: editable area'}</figcaption><div className="face-stage"><img src={photo.url} alt="Original uploaded reference" />{!job && <svg viewBox={`0 0 ${photo.width} ${photo.height}`} aria-label="Face and edit region selection" onPointerDown={e=>{if(!busy){drag.current=point(e);e.currentTarget.setPointerCapture(e.pointerId);}}} onPointerMove={move} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}}><rect x={face[0]} y={face[1]} width={Math.max(0,face[2]-face[0])} height={Math.max(0,face[3]-face[1])} fill="none" stroke="white" strokeWidth="3" strokeDasharray="8 5"/><ellipse cx={(edit[0]+edit[2])/2} cy={(edit[1]+edit[3])/2} rx={Math.max(0,(edit[2]-edit[0])/2)} ry={Math.max(0,(edit[3]-edit[1])/2)} fill="#a88bd977" stroke="#513775" strokeWidth="2"/></svg>}</div></figure>
        {job?.status==='completed' && <figure><figcaption>AI preview · illustrative only</figcaption><div className="face-stage" style={{aspectRatio:`${photo.width}/${photo.height}`,overflow:'hidden'}}><img src={job.imageUrl} alt="AI edited facial area, not an expected product outcome" onError={()=>setError('Preview expired or could not load. Delete it and generate again.')} /></div><p className="small-text">Same framing. Pixels outside your selection are preserved. The selected area can still contain AI artifacts.</p><a href={job.imageUrl} download="rest-ai-illustration.png">Download labeled illustration</a></figure>}
        {job?.status==='completed' && previewProduct && <PreviewProductCard product={previewProduct} />}
      </div>
      {!job && <fieldset disabled={busy}>
        <details><summary>Precise selection coordinates (keyboard controls)</summary>{(['face','edit'] as const).map(kind=><div key={kind}><strong>{kind==='face'?'Face square':'Edit ellipse'}</strong><div className="face-coordinates">{['Left','Top','Right','Bottom'].map((label,i)=><label key={label}>{label}<input type="number" aria-label={`${kind} ${label}`} value={(kind==='face'?face:edit)[i]} min="0" max={i%2===0?photo.width:photo.height} onChange={e=>{const box:Box=[...(kind==='face'?face:edit)];box[i]=Number(e.target.value);(kind==='face'?setFace:setEdit)(box);setConsent(false);}} /></label>)}</div></div>)}</details>
        <div className="face-tools"><label className="field">Edit amount<select value={strength} onChange={e=>setStrength(e.target.value)}><option value="0.15">Subtle</option><option value="0.25">Moderate</option></select></label><label className="field">Shading / lighting<select value={finish} onChange={e=>setFinish(e.target.value)}><option value="original">No added lighting effect</option><option value="soft-light">Gentle brightening inside selection</option></select></label></div>
        <label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>I checked both regions and agree to send this photo to the {cloudEnabled ? 'Rest cloud preview service in AWS Ohio' : 'local preview service'}. This is an illustration, not a product outcome.</label>
        <button className="button primary" disabled={!consent||busy} onClick={()=>void generate()}>Create AI preview</button>
      </fieldset>}
      {busy && <p role="status">{job?.status==='queued'?'Queued for the model…':'Creating your selected face-area preview…'}</p>}
      {(job||busy) && <button className="button secondary" onClick={()=>void clear().catch(e=>setError(e.message))}>{busy?'Cancel preview':'Delete preview / edit selection'}</button>}
    </>}
    <p className="small-text">{cloudEnabled ? 'Cloud preview. Your photo is temporarily processed on the Rest server.' : 'Local development preview.'} Uploads are resized to 1,024 pixels and metadata is removed. The service deletes input photos after processing; previews expire after 30 minutes or can be deleted above. Photos are not used for training.</p>
  </section>;
}
