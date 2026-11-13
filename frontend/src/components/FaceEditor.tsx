import { useEffect, useRef, useState, type PointerEvent } from 'react';
import { createIllustration, getIllustration, deleteIllustration, releaseIllustrationImage, cloudEnabled, type Box, type IllustrationJob } from '../services/illustration';
import './face-editor.css';
import { PreviewInputs } from './PreviewInputs';
import { CloudSignIn } from './CloudSignIn';
import { supabase } from '../services/cloudSession';
import { ArrowRight, Download, ImagePlus, Sparkles } from 'lucide-react';
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
  const [view, setView] = useState<'slider' | 'side'>('slider');
  const [reveal, setReveal] = useState(50);
  const [elapsed, setElapsed] = useState(0);
  const current = useRef<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  const alive = useRef(true);
  const drag = useRef<[number,number] | null>(null);
  const workspace = useRef<HTMLDivElement | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; controller.current?.abort(); if (current.current) void deleteIllustration(current.current).catch(()=>{}); }; }, []);
  useEffect(() => () => { if (photo) URL.revokeObjectURL(photo.url); }, [photo]);
  useEffect(() => {
    if (job?.status === 'completed') workspace.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [job?.status]);
  useEffect(() => {
    if (!busy) return;
    const started = Date.now(); setElapsed(0);
    const timer = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);
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
  const step = !photo ? 1 : job?.status === 'completed' ? 4 : busy ? 3 : 2;
  const ratio = photo ? photo.width / photo.height : 1;
  const steps = ['Add a photo', 'Select an area', 'Create', 'Review'];
  return <section className="panel face-editor">
    <div className="fe-head">
      <span className="eyebrow">AI PREVIEW</span>
      <h2>See a small, gentle change.</h2>
      <p>Choose one small skin area and see an illustration of a softer look. Everything outside your selection stays exactly the same.</p>
    </div>
    {/* Step tracker so people always know where they are in the flow. */}
    <ol className="fe-steps" aria-label="Preview steps">
      {steps.map((label, i) => <li key={label} className={i + 1 < step ? 'done' : i + 1 === step ? 'active' : ''} aria-current={i + 1 === step ? 'step' : undefined}><span>{i + 1 < step ? '✓' : i + 1}</span>{label}</li>)}
    </ol>
    {cloudEnabled && <CloudSignIn />}
    {error && <p className="notice error" role="alert">{error}</p>}
    {!photo ? <>
      <label className="photo-upload fe-drop">
        <span className="icon-orbit"><ImagePlus size={27} /></span>
        <strong>Add a clear, front-facing photo</strong>
        <span>JPG, PNG or WebP · up to 10 MB · resized and stripped of metadata</span>
        <span className="button secondary">Choose a photo <ArrowRight size={16} /></span>
        <input aria-label="Upload preview photo" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={e=>{void upload(e.target.files?.[0]);e.target.value='';}} />
      </label>
      <PreviewInputs />
    </> : <div className="fe-workspace" ref={workspace}>
      <div className="fe-canvas">
        {job?.status === 'completed' && job.imageUrl ? (view === 'slider'
          ? <div className="comparison-stage fe-compare" style={{aspectRatio: `${photo.width}/${photo.height}`, width: `min(100%, calc(72vh * ${ratio}))`}}>
              <img src={job.imageUrl} alt="AI edited facial area, not an expected product outcome" onError={()=>setError('Preview expired or could not load. Delete it and generate again.')} />
              <img className="before-layer" src={photo.url} alt="Original uploaded reference" style={{clipPath: `inset(0 ${100 - reveal}% 0 0)`}} />
              <div className="slider-divider" style={{left: `${reveal}%`}}><span>↔</span></div>
              <span className="photo-label left">Original</span><span className="photo-label right">AI preview</span>
              <input className="fe-reveal" aria-label="Compare original and AI preview" type="range" min="0" max="100" value={reveal} onChange={e=>setReveal(Number(e.target.value))} />
            </div>
          : <div className="fe-pair">
              <figure><figcaption>Original</figcaption><img src={photo.url} alt="Original uploaded reference" /></figure>
              <figure><figcaption>AI preview · illustrative only</figcaption><img src={job.imageUrl} alt="AI edited facial area, not an expected product outcome" /></figure>
            </div>)
        : <div className={`face-stage${busy ? ' working' : ''}`}>
            <img src={photo.url} alt="Original uploaded reference" />
            {!job && <svg viewBox={`0 0 ${photo.width} ${photo.height}`} aria-label="Face and edit region selection" onPointerDown={e=>{if(!busy){drag.current=point(e);e.currentTarget.setPointerCapture(e.pointerId);}}} onPointerMove={move} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}}><rect x={face[0]} y={face[1]} width={Math.max(0,face[2]-face[0])} height={Math.max(0,face[3]-face[1])} fill="none" stroke="white" strokeWidth={Math.max(2, photo.width/300)} strokeDasharray="8 5"/><ellipse cx={(edit[0]+edit[2])/2} cy={(edit[1]+edit[3])/2} rx={Math.max(0,(edit[2]-edit[0])/2)} ry={Math.max(0,(edit[3]-edit[1])/2)} fill="#a88bd977" stroke="#513775" strokeWidth={Math.max(2, photo.width/400)}/></svg>}
            {busy && <div className="fe-working-overlay" aria-hidden="true"><span className="fe-spinner" /></div>}
          </div>}
        {job?.status === 'completed' && <p className="small-text fe-caption">Same framing. Pixels outside your selection are preserved. The selected area can still contain AI artifacts.</p>}
      </div>

      <div className="fe-controls">
        {!job && !busy && <fieldset className="fe-card">
          <legend>1 · Select the area</legend>
          <div className="segmented fe-seg" role="group" aria-label="Selection tool">
            <button aria-pressed={selection==='face'} className={selection==='face'?'active':''} onClick={()=>setSelection('face')}>Frame face</button>
            <button aria-pressed={selection==='edit'} className={selection==='edit'?'active':''} onClick={()=>setSelection('edit')}>Edit area</button>
          </div>
          <p className="small-text">{selection==='face' ? 'Drag a square around your face on the photo.' : 'Draw an oval over skin only. Keep eyes, lips and hair outside it.'}</p>
          <details><summary>Exact coordinates (keyboard)</summary>{(['face','edit'] as const).map(kind=><div key={kind}><strong>{kind==='face'?'Face square':'Edit ellipse'}</strong><div className="face-coordinates">{['Left','Top','Right','Bottom'].map((label,i)=><label key={label}>{label}<input type="number" aria-label={`${kind} ${label}`} value={(kind==='face'?face:edit)[i]} min="0" max={i%2===0?photo.width:photo.height} onChange={e=>{const box:Box=[...(kind==='face'?face:edit)];box[i]=Number(e.target.value);(kind==='face'?setFace:setEdit)(box);setConsent(false);}} /></label>)}</div></div>)}</details>
        </fieldset>}

        {!job && !busy && <fieldset className="fe-card">
          <legend>2 · Choose the look</legend>
          <span className="fe-label">Edit amount</span>
          <div className="segmented fe-seg" role="group" aria-label="Edit amount">
            <button aria-pressed={strength==='0.15'} className={strength==='0.15'?'active':''} onClick={()=>setStrength('0.15')}>Subtle</button>
            <button aria-pressed={strength==='0.25'} className={strength==='0.25'?'active':''} onClick={()=>setStrength('0.25')}>Moderate</button>
          </div>
          <span className="fe-label">Lighting</span>
          <div className="segmented fe-seg" role="group" aria-label="Lighting">
            <button aria-pressed={finish==='original'} className={finish==='original'?'active':''} onClick={()=>setFinish('original')}>Natural</button>
            <button aria-pressed={finish==='soft-light'} className={finish==='soft-light'?'active':''} onClick={()=>setFinish('soft-light')}>Gentle brightening</button>
          </div>
          <PreviewProductPicker value={product} onChange={setProduct} disabled={busy} />
        </fieldset>}

        {!job && !busy && <div className="fe-card fe-create">
          <label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/>I checked both regions and agree to send this photo to the {cloudEnabled ? 'Rest cloud preview service in AWS Ohio' : 'local preview service'}. This is an illustration, not a product outcome.</label>
          <button className="button primary" disabled={!consent} onClick={()=>void generate()}><Sparkles size={16} /> Create AI preview</button>
          <label className="fe-change">Use a different photo<input aria-label="Replace preview photo" type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>{void upload(e.target.files?.[0]);e.target.value='';}} /></label>
        </div>}

        {busy && <div className="fe-card" role="status">
          <strong className="fe-card-title">{job?.status==='queued' ? 'Waiting for the model…' : 'Creating your preview…'}</strong>
          <div className={`fe-progress${typeof job?.progress === 'number' ? '' : ' indeterminate'}`}><span style={typeof job?.progress === 'number' ? {width: `${job.progress}%`} : undefined} /></div>
          <p className="small-text">{elapsed}s elapsed · only your selected area is being edited. This usually takes under a minute.</p>
          <button className="button secondary" onClick={()=>void clear().catch(e=>setError(e.message))}>Cancel preview</button>
        </div>}

        {job?.status === 'completed' && <div className="fe-card">
          <strong className="fe-card-title">Your preview is ready</strong>
          <div className="segmented fe-seg" role="group" aria-label="Comparison view">
            <button aria-pressed={view==='slider'} className={view==='slider'?'active':''} onClick={()=>setView('slider')}>Slider</button>
            <button aria-pressed={view==='side'} className={view==='side'?'active':''} onClick={()=>setView('side')}>Side by side</button>
          </div>
          {previewProduct && <PreviewProductCard product={previewProduct} />}
          <div className="fe-actions">
            <a className="button primary" href={job.imageUrl} download="rest-ai-illustration.png"><Download size={16} /> Download</a>
            <button className="button secondary" onClick={()=>void clear().catch(e=>setError(e.message))}>Edit selection</button>
          </div>
        </div>}
      </div>
    </div>}
    <p className="notice fe-notice"><strong>AI illustration—not a product result.</strong> This preview cannot show what a product will do to your skin. Use two real dated photos in My photo comparison to record actual progress.</p>
    <p className="small-text">{cloudEnabled ? 'Cloud preview. Your photo is temporarily processed on the Rest server.' : 'Local development preview.'} Uploads are resized to 1,024 pixels and metadata is removed. The service deletes input photos after processing; previews expire after 30 minutes or can be deleted above. Photos are not used for training.</p>
  </section>;
}
