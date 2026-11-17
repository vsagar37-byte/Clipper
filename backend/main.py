import sys
if sys.version_info < (3, 10):
    raise SystemExit(f'ClipForge requires Python 3.10 or newer. This interpreter is {sys.version.split()[0]}.')

import json, os, re, shutil, subprocess, threading, time, uuid
from hmac import compare_digest
from pathlib import Path
from collections import Counter
from urllib.parse import parse_qs, urlsplit
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
if not (ROOT / 'frontend').is_dir():
    ROOT = ROOT.parent
DATA = Path(os.getenv('CLIPFORGE_DATA', ROOT / 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_MB', '500')) * 1024 * 1024
MAX_DURATION = int(os.getenv('MAX_DURATION_SECONDS', '3600'))
JOBS = {}
IMPORT_SLOT = threading.BoundedSemaphore(1)
app = FastAPI(title='ClipForge API', version='0.5.0')


@app.middleware('http')
async def require_api_access(request: Request, call_next):
    path = request.url.path
    if not path.startswith('/api/') or (path == '/api/health' and request.method == 'GET'):
        return await call_next(request)

    key = os.getenv('CLIPFORGE_ACCESS_KEY', '')
    required = os.getenv('CLIPFORGE_REQUIRE_ACCESS_KEY') == '1'
    if required and len(key) < 32:
        return JSONResponse({'detail': 'Backend access key is not configured.'}, status_code=503)
    if key:
        supplied = request.headers.get('authorization', '')
        if not compare_digest(supplied.encode('utf-8'), f'Bearer {key}'.encode('utf-8')):
            return JSONResponse(
                {'detail': 'Enter the backend access key and reconnect.'},
                status_code=401,
                headers={'WWW-Authenticate': 'Bearer'},
            )
    return await call_next(request)


app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS','http://localhost,https://localhost,http://127.0.0.1:8000').split(','), allow_methods=['*'], allow_headers=['*'])

def run(args, timeout=240, cwd=None):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=True, cwd=cwd)

def probe(path):
    info=json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]).stdout)
    duration=float(info.get('format',{}).get('duration',0))
    video=next((s for s in info.get('streams',[]) if s.get('codec_type')=='video'),None)
    if not video or duration<=0 or duration>MAX_DURATION:
        raise ValueError('Invalid video or duration exceeds limit')
    return {'duration':round(duration,2),'width':int(video['width']),'height':int(video['height']), 'has_audio':any(s.get('codec_type')=='audio' for s in info.get('streams',[]))}

def source(vid):
    if not re.fullmatch(r'[a-f0-9]{32}',vid): raise HTTPException(400,'Invalid ID')
    path=DATA/vid/'source.mp4'
    if not path.exists(): raise HTTPException(404,'Video not found')
    return path

@app.get('/api/health')
def health():
    media_tools_ready = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
    access_ready = (
        os.getenv('CLIPFORGE_REQUIRE_ACCESS_KEY') != '1'
        or len(os.getenv('CLIPFORGE_ACCESS_KEY', '')) >= 32
    )
    ready = media_tools_ready and access_ready
    return JSONResponse(
        {'status': 'ok' if ready else 'unavailable', 'ffmpeg': media_tools_ready,
         'transcription_available': _whisper_available()},
        status_code=200 if ready else 503,
    )


@app.get('/api/access')
def access():
    return {'status': 'ok'}

def _whisper_available():
    try:
        import faster_whisper
        return True
    except ImportError: return False

class YouTubeLink(BaseModel):
    url: str = Field(max_length=2048)


def youtube_video_id(url: str) -> str:
    try:
        parsed = urlsplit(url.strip())
        host = parsed.netloc.lower()
        video_id = ''
        if parsed.scheme == 'https':
            if host == 'youtu.be':
                video_id = parsed.path.removeprefix('/')
            elif host in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
                if parsed.path == '/watch':
                    values = parse_qs(parsed.query, keep_blank_values=True).get('v', [])
                    if len(values) == 1:
                        video_id = values[0]
                elif parsed.path.startswith('/shorts/'):
                    video_id = parsed.path.removeprefix('/shorts/')
        if len(url) <= 2048 and re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            return video_id
    except ValueError:
        pass
    raise HTTPException(400, 'Enter an HTTPS YouTube watch, Shorts, or youtu.be video link.')


@app.post('/api/import/youtube/validate')
def validate_youtube_link(link: YouTubeLink):
    video_id = youtube_video_id(link.url)
    return {'studio_url': f'https://studio.youtube.com/video/{video_id}/edit'}


@app.post('/api/import/youtube', status_code=202)
def import_youtube(link: YouTubeLink, background: BackgroundTasks):
    video_id = youtube_video_id(link.url)
    if not IMPORT_SLOT.acquire(blocking=False):
        raise HTTPException(429, 'Another YouTube import is running. Wait for it to finish.')
    job = uuid.uuid4().hex
    JOBS[job] = {'status': 'processing', 'stage': 'Downloading from YouTube'}
    background.add_task(youtube_import_worker, job, video_id)
    return {'job_id': job, 'status': 'processing'}


def youtube_import_worker(job, video_id):
    from backend.youtube_import import download_youtube
    vid = uuid.uuid4().hex
    folder = DATA / vid
    try:
        folder.mkdir()
        details = download_youtube(video_id, folder, MAX_UPLOAD, MAX_DURATION)
        meta = {**probe(folder / 'source.mp4'), **details}
        (folder / 'meta.json').write_text(json.dumps(meta))
        JOBS[job] = {'status': 'done', 'video': {
            'id': vid, **meta, 'video_url': f'/api/videos/{vid}/source'}}
    except Exception as exc:
        shutil.rmtree(folder, ignore_errors=True)
        message = str(exc) if isinstance(exc, ValueError) else 'Import failed. Check server dependencies or upload the original video file.'
        JOBS[job] = {'status': 'error', 'error': message}
    finally:
        IMPORT_SLOT.release()


@app.post('/api/upload')
async def upload(
    file: UploadFile = File(...),
    youtube_url: str | None = Form(None),
    authorized: bool = Form(False),
):
    youtube_id = None
    if youtube_url is not None:
        youtube_id = youtube_video_id(youtube_url)
        if not authorized:
            raise HTTPException(403, 'Confirm you have permission to use this video file.')
    vid=uuid.uuid4().hex; folder=DATA/vid; folder.mkdir()
    path=folder/'source.mp4'; total=0
    try:
        with path.open('wb') as f:
            while chunk:=await file.read(1024*1024):
                total+=len(chunk)
                if total>MAX_UPLOAD: raise ValueError('File exceeds upload limit')
                f.write(chunk)
        meta=probe(path)
        if youtube_id:
            meta['youtube_video_id'] = youtube_id
        (folder/'meta.json').write_text(json.dumps(meta))
        return {'id':vid,**meta,'video_url':f'/api/videos/{vid}/source'}
    except (ValueError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        shutil.rmtree(folder,ignore_errors=True)
        raise HTTPException(400,str(e))

@app.get('/api/videos/{vid}/source')
def video_file(vid:str):
    return FileResponse(source(vid),media_type='video/mp4')

class AnalyzeRequest(BaseModel):
    clip_length:int=Field(default=30,ge=5,le=120)
    count:int=Field(default=5,ge=1,le=12)
    transcribe:bool=False

def transcript_segments(path):
    from faster_whisper import WhisperModel
    model=WhisperModel(os.getenv('WHISPER_MODEL','tiny'),device='cpu',compute_type='int8')
    segments,_=model.transcribe(str(path),vad_filter=True,word_timestamps=True)
    return [{'start':s.start,'end':s.end,'text':s.text.strip(),'words':[{'start':w.start,'end':w.end,'text':w.word.strip()} for w in (s.words or []) if w.start is not None and w.end is not None]} for s in segments]

def detect_scenes(path):
    try:
        p=run(['ffmpeg','-hide_banner','-i',str(path),'-vf',"scale=320:-1,select='gt(scene,0.3)',showinfo",'-an','-f','null','-'],timeout=120)
        log=p.stderr
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
        log=getattr(e,'stderr','') or ''
    return [float(x) for x in re.findall(r'pts_time:([0-9.]+)',log)]

def detect_silence(path):
    try:
        p=run(['ffmpeg','-hide_banner','-i',str(path),'-af','silencedetect=noise=-32dB:d=0.5','-f','null','-'],timeout=120)
        log=p.stderr
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
        log=getattr(e,'stderr','') or ''
    return [(float(a),float(b)) for a,b in re.findall(r'silence_start: ([0-9.]+).*?silence_end: ([0-9.]+)',log,re.S)]

HOOK_WORDS={'why','how','secret','never','stop','mistake','best','worst','wait','look','what','amazing','shocking','important','చూడండి','ఎందుకు','कैसे','क्यों'}
def make_suggestions(meta, scenes, silences, transcript, length, count):
    dur=meta['duration']; length=min(length,dur)
    starts=[0.0]
    starts += [max(0,min(dur-length,t-1.5)) for t in scenes]
    starts += [max(0,min(dur-length,t-1.5)) for t in [x['start'] for x in transcript]]
    step=max(3,length/2)
    starts += [min(dur-length,i*step) for i in range(int(max(0,dur-length)//step)+1)]
    ranked=[]
    for start in sorted(set(round(s,1) for s in starts)):
        end=start+length
        scene_count=sum(start<=t<end for t in scenes)
        silence_seconds=sum(max(0,min(end,b)-max(start,a)) for a,b in silences)
        words=' '.join(s['text'] for s in transcript if s['end']>=start and s['start']<end)
        hooks=sum(w in words.lower().split() for w in HOOK_WORDS)
        speech_count=sum(s['end']>=start and s['start']<end for s in transcript)
        score=round(min(99,35+min(scene_count,8)*6+min(speech_count,8)*3+min(hooks,3)*9-30*silence_seconds/max(length,1)))
        ranked.append({'start':round(start,2),'end':round(end,2),'score':max(1,score),'reason':f'{scene_count} visual changes · {speech_count} speech segments · {hooks} hook terms','transcript':words[:500]})
    ranked.sort(key=lambda x:x['score'],reverse=True)
    chosen=[]
    for c in ranked:
        if all(abs(c['start']-x['start'])>=length*.65 for x in chosen): chosen.append(c)
        if len(chosen)>=count: break
    return chosen

@app.post('/api/videos/{vid}/analyze')
def analyze(vid:str,req:AnalyzeRequest):
    path=source(vid); meta=json.loads((path.parent/'meta.json').read_text())
    scenes=detect_scenes(path)
    silences=detect_silence(path) if meta['has_audio'] else []
    transcript=[]; warning=None
    if req.transcribe:
        if _whisper_available():
            try: transcript=transcript_segments(path)
            except Exception as e: warning=f'Transcription failed: {e}'
        else: warning='Install faster-whisper to enable speech-aware ranking and captions.'
    return {'suggestions':make_suggestions(meta,scenes,silences,transcript,req.clip_length,req.count),'transcript':transcript,'warning':warning,'method':'Heuristic visual/audio ranking; not a validated virality prediction'}

@app.post('/api/videos/{vid}/transcribe')
def transcribe_for_editor(vid:str):
    path=source(vid)
    if not _whisper_available(): raise HTTPException(503,'Install faster-whisper to transcribe speech, or add captions manually in the timeline')
    try: return {'segments':transcript_segments(path)}
    except Exception as e: raise HTTPException(500,str(e))

class ExportRequest(BaseModel):
    start:float=Field(ge=0)
    end:float=Field(gt=0)
    aspect:str='9:16'
    subtitles:bool=False
    transcript:list[dict]=Field(default_factory=list)
    caption_style:str='classic'
    caption_color:str='#FFFFFF'
    caption_highlight:str='#FFE55C'
    caption_font:str='Arial'
    caption_position:str='bottom'
    caption_font_size:int=Field(default=52,ge=20,le=100)
    word_highlight:bool=False
    caption_animation:str="none"

def srt_timestamp(seconds):
    ms=int(seconds*1000); h,ms=divmod(ms,3600000); m,ms=divmod(ms,60000); s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def write_srt(path,segments,start,end):
    lines=[]
    for s in segments:
        a=max(start,float(s.get('start',0))); b=min(end,float(s.get('end',0)))
        if b<=a: continue
        txt=str(s.get('text','')).strip().replace('\n',' ')
        if not txt: continue
        lines.append(f'{len(lines)+1}\n{srt_timestamp(a-start)} --> {srt_timestamp(b-start)}\n{txt}\n')
    path.write_text('\n'.join(lines),encoding='utf-8')
    return bool(lines)

CAPTION_STYLES={'classic','bold','outline','neon'}
CAPTION_FONTS={'Arial','DejaVu Sans','Liberation Sans','Noto Sans','Noto Sans Telugu','Noto Sans Devanagari'}
CAPTION_POSITIONS={'top','center','bottom'}
CAPTION_ANIMATIONS={'none','fade','pop'}

def ass_color(hexcolor):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',hexcolor): raise ValueError('Invalid caption color')
    return '&H00'+hexcolor[5:7]+hexcolor[3:5]+hexcolor[1:3].upper()

def ass_time(t):
    cs=max(0,int(round(t*100))); h,cs=divmod(cs,360000); m,cs=divmod(cs,6000); sec,cs=divmod(cs,100)
    return f'{h}:{m:02}:{sec:02}.{cs:02}'

def ass_escape(t):
    return str(t).replace('\\','').replace('{','').replace('}','').replace('\n',' ')

def write_animated_ass(path, segments, start, end, req, width, height):
    primary=ass_color(req.caption_color); highlight=ass_color(req.caption_highlight)
    alignment={'bottom':2,'center':5,'top':8}[req.caption_position]
    margin=int(height*({'bottom':.10,'center':.03,'top':.10}[req.caption_position]))
    fontsize=max(16,round(req.caption_font_size*height/1920))
    outline={'classic':3,'bold':4,'outline':6,'neon':4}[req.caption_style]
    shadow={'classic':1,'bold':2,'outline':0,'neon':3}[req.caption_style]
    style=f'Style: Default,{req.caption_font},{fontsize},{primary},&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},{alignment},40,40,{margin},1'
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: WIDTH
PlayResY: HEIGHT
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
STYLE

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""".replace('WIDTH',str(width)).replace('HEIGHT',str(height)).replace('STYLE',style)
    events=[]
    def add(a,b,txt):
        if b>a and txt.strip(): events.append(f'Dialogue: 0,{ass_time(a-start)},{ass_time(b-start)},Default,,0,0,0,,{txt}')
    for seg in segments:
        a=max(start,float(seg.get('start',0))); b=min(end,float(seg.get('end',0)))
        if b<=a:continue
        words=[w for w in seg.get('words',[]) if float(w.get('end',0))>a and float(w.get('start',0))<b and str(w.get('text','')).strip()]
        animation={'none':'','fade':r'{\fad(140,140)}','pop':r'{\fscx85\fscy85\t(0,160,\fscx100\fscy100)}'}[req.caption_animation]
        if req.word_highlight and words:
            # Each word is emphasized only for its actual speech interval; other words remain visible.
            plain=[ass_escape(w['text']) for w in words]
            for i,w in enumerate(words):
                wa=max(a,float(w['start'])); wb=min(b,float(w['end']))
                if wb<=wa:continue
                pieces=[(f'{{\\c{highlight}\\b1}}{word}{{\\c{primary}\\b1}}' if k==i else word) for k,word in enumerate(plain)]
                add(wa,wb,animation+' '.join(pieces))
        else:
            add(a,b,animation+ass_escape(seg.get('text','')))
    if not events:return False
    path.write_text(header+'\n'.join(events)+'\n',encoding='utf-8')
    return True

def export_worker(job,vid,req):
    path=source(vid); folder=path.parent; out=folder/f'{job}.mp4'
    try:
        meta=json.loads((folder/'meta.json').read_text())
        if req.end<=req.start or req.end>meta['duration']+.1: raise ValueError('Invalid trim range')
        w,h=(1080,1920) if req.aspect=='9:16' else ((1920,1080) if req.aspect=='16:9' else (1080,1080))
        vf=f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1'
        if req.subtitles:
            segments=req.transcript
            if not segments:
                if not meta['has_audio']: raise ValueError('Auto Captions requires a video with audio')
                if not _whisper_available(): raise ValueError('Install faster-whisper to enable Auto Captions')
                segments=transcript_segments(path)
            if not segments: raise ValueError('No speech detected for captions')
            srt=folder/f'{job}.srt'
            write_srt(srt,segments,req.start,req.end)
            ass=folder/f'{job}.ass'
            if not write_animated_ass(ass,segments,req.start,req.end,req,w,h):
                raise ValueError('No captions overlap the selected clip')
            vf+=f',ass={ass.name}'
        cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-ss',str(req.start),'-i',str(path),'-t',str(req.end-req.start),'-vf',vf,'-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p']
        if meta['has_audio']: cmd+=['-c:a','aac','-b:a','128k']
        else: cmd+=['-an']
        cmd+=['-movflags','+faststart',str(out)]
        run(cmd,timeout=900,cwd=folder)
        JOBS[job]={'status':'done','url':f'/api/exports/{vid}/{job}','srt_url':f'/api/exports/{vid}/{job}/captions' if req.subtitles else None}
    except Exception as e: JOBS[job]={'status':'error','error':str(e)}

@app.post('/api/videos/{vid}/export')
def export(vid:str,req:ExportRequest,background:BackgroundTasks):
    source(vid)
    if req.aspect not in ('9:16','16:9','1:1'): raise HTTPException(400,'Unsupported aspect')
    if req.caption_style not in CAPTION_STYLES or req.caption_font not in CAPTION_FONTS or req.caption_position not in CAPTION_POSITIONS or req.caption_animation not in CAPTION_ANIMATIONS: raise HTTPException(400,'Unsupported caption styling')
    try: ass_color(req.caption_color); ass_color(req.caption_highlight)
    except ValueError as e: raise HTTPException(400,str(e))
    job=uuid.uuid4().hex; JOBS[job]={'status':'processing'}
    background.add_task(export_worker,job,vid,req)
    return {'job_id':job,'status':'processing'}

@app.get('/api/jobs/{job}')
def job_status(job:str):
    return JOBS.get(job,{'status':'not_found'})

@app.get('/api/exports/{vid}/{job}')
def download(vid:str,job:str):
    source(vid)
    if not re.fullmatch(r'[a-f0-9]{32}',job): raise HTTPException(400,'Invalid job')
    path=DATA/vid/f'{job}.mp4'
    if not path.exists(): raise HTTPException(404,'Export not ready')
    return FileResponse(path,media_type='video/mp4',filename='clipforge-export.mp4')

@app.get('/api/exports/{vid}/{job}/captions')
def download_captions(vid:str,job:str):
    source(vid)
    if not re.fullmatch(r'[a-f0-9]{32}',job): raise HTTPException(400,'Invalid job')
    path=DATA/vid/f'{job}.srt'
    if not path.exists(): raise HTTPException(404,'Captions not ready')
    return FileResponse(path,media_type='text/plain',filename='clipforge-captions.srt')

app.mount('/',StaticFiles(directory=str(ROOT/'frontend'),html=True),name='frontend')
