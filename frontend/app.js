// ClipForge AI Android web controller
const $=id=>document.getElementById(id);
let videoId=null,transcript=[],selected=-1;
const backend=()=>localStorage.getItem('clipforge_api_url')||window.CLIPFORGE_API_URL||'';
let accessKey = '';
const request = (path, opts = {}) => {
    const headers = new Headers(opts.headers);
    if (accessKey) headers.set('Authorization', 'Bearer ' + accessKey);
    return fetch(backend().replace(/\/$/, '') + path, {...opts, headers, redirect: 'error'});
};
const api=async(path,opts={})=>{const r=await request(path,opts);const data=await r.json().catch(()=>null);if(!r.ok||!data)throw Error(typeof data?.detail==='string'?data.detail:'Request failed ('+r.status+')');return data};
const msg=(id,value)=>{const e=$(id);if(e)e.textContent=value};
async function health() {
    try {
        const response = await request('/api/health');
        const status = await response.json().catch(() => null);
        if (!status) throw Error('Backend did not return a health status.');
        if (!status.ffmpeg) {
            msg('server', 'FFmpeg unavailable');
            msg('backendStatus', 'Connected. Install FFmpeg and FFprobe on the server.');
            return;
        }
        if (!response.ok) {
            throw Error(typeof status.detail === 'string' ? status.detail : 'Backend is unavailable.');
        }
        await api('/api/access');
        msg('server', 'Engine online');
        msg('backendStatus', 'Connected');
    } catch (error) {
        msg('server', 'Connection unavailable');
        msg('backendStatus', error.message);
    }
}
$('backendUrl').value = backend();
$('saveBackend').onclick = () => {
    const value = $('backendUrl').value.trim();
    const key = $('backendKey').value.trim();
    try {
        const destination = new URL(value || location.origin);
        if (value && (!['http:', 'https:'].includes(destination.protocol) ||
            destination.username || destination.password || destination.pathname !== '/' ||
            destination.search || destination.hash)) throw Error('Enter the backend origin.');
        if (key && destination.protocol !== 'https:' &&
            !['localhost', '127.0.0.1', '[::1]'].includes(destination.hostname)) {
            throw Error('Use an HTTPS backend URL when sending an access key.');
        }
        if ((value ? destination.origin : '') !== backend()) {
            videoId = null;
            for (const id of editorActions) $(id).disabled = true;
            for (const id of ['download', 'srtDownload']) $(id).classList.add('hidden');
        }
        accessKey = key;
        localStorage.setItem('clipforge_api_url', value ? destination.origin : '');
        $('backendKey').value = '';
        health();
    } catch (error) {
        msg('backendStatus', error.message);
    }
};

function offerDownload(id, path, filename) {
    const link = $(id);
    link.onclick = async event => {
        event.preventDefault();
        try {
            const response = await request(path);
            if (!response.ok) throw Error('Download unavailable. Check your backend connection.');
            const url = URL.createObjectURL(await response.blob());
            const download = document.createElement('a');
            download.href = url;
            download.download = filename;
            document.body.append(download);
            download.click();
            download.remove();
            setTimeout(() => URL.revokeObjectURL(url), 60000);
        } catch (error) {
            msg('exportStatus', error.message);
        }
    };
    link.href = '#';
    link.classList.remove('hidden');
}
let objectUrl = '';
const editorActions = ['analyze', 'generateCaptions', 'addCaption', 'export'];
const jsonHeaders = {'Content-Type': 'application/json'};

$('youtubeForm').onsubmit = async event => {
    event.preventDefault();
    const locked = [...editorActions, 'file', 'youtubeUrl', 'checkYouTube', 'saveBackend'];
    const previous = locked.map(id => $(id).disabled);
    locked.forEach(id => $(id).disabled = true);
    let ready = false;
    try {
        msg('youtubeStatus', 'Importing video from YouTube…');
        const started = await api('/api/import/youtube', {
            method: 'POST', headers: jsonHeaders,
            body: JSON.stringify({url: $('youtubeUrl').value.trim()})
        });
        const deadline = Date.now() + 16 * 60 * 1000;
        let video;
        while (Date.now() < deadline) {
            await new Promise(resolve => setTimeout(resolve, 2000));
            const job = await api('/api/jobs/' + started.job_id);
            if (job.status === 'error') throw Error(job.error);
            if (job.status === 'not_found') throw Error('Import was lost after a server restart. Try again.');
            if (job.status === 'done') { video = job.video; break; }
            msg('youtubeStatus', job.stage || 'Importing…');
        }
        if (!video) throw Error('Import did not finish in time. Try again later.');
        msg('youtubeStatus', 'Loading video preview…');
        const response = await request(video.video_url);
        if (!response.ok) throw Error('Could not load imported video. Check your connection.');
        loadVideo(video, await response.blob(), video.title);
        ready = true;
        msg('youtubeStatus', 'Imported. Finding highlight suggestions…');
        await $('analyze').onclick();
        msg('youtubeStatus', 'Video ready. Review the suggested moments and export your clips.');
    } catch (error) {
        msg('youtubeStatus', error.message);
    } finally {
        locked.forEach((id, i) => $(id).disabled = ready && editorActions.includes(id) ? false : previous[i]);
    }
};

function loadVideo(video, blob, name) {
    videoId = video.id;
    transcript = [];
    selected = -1;
    drawCaptions();
    $('captionEditor').classList.add('hidden');
    $('suggestions').replaceChildren();
    for (const id of ['download', 'srtDownload']) $(id).classList.add('hidden');
    msg('analysisStatus', '');
    msg('exportStatus', 'Choose your cut to export.');
    $('start').value = $('rangeStart').value = 0;
    $('rangeStart').max = $('rangeEnd').max = video.duration;
    $('end').value = $('rangeEnd').value = Math.min(30, video.duration).toFixed(1);
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(blob);
    $('player').src = objectUrl;
    $('player').classList.add('visible');
    $('placeholder').style.display = 'none';
    msg('meta', name);
    msg('uploadStatus', 'Video ready');
}

async function uploadVideo(input) {
    const file = input.files[0];
    if (!file) return;
    const previous = editorActions.map(id => $(id).disabled);
    const locked = [...editorActions, 'file', 'youtubeUrl', 'checkYouTube', 'saveBackend'];
    for (const id of locked) $(id).disabled = true;
    let ready = false;
    try {
        msg('uploadStatus', 'Uploading ' + file.name + '…');
        const form = new FormData();
        form.append('file', file);
        const video = await api('/api/upload', {method: 'POST', body: form});
        loadVideo(video, file, file.name);
        ready = true;
    } catch (error) {
        msg('uploadStatus', error.message);
    } finally {
        input.value = '';
        for (const id of locked) $(id).disabled = false;
        editorActions.forEach((id, index) => { $(id).disabled = !ready && previous[index]; });
    }
}

$('file').onchange = event => uploadVideo(event.target);
function setTrim(start, end) {
    $('start').value = $('rangeStart').value = start;
    $('end').value = $('rangeEnd').value = end;
}
$('markStart').onclick=()=>setTrim($('player').currentTime.toFixed(1), $('end').value);
$('markEnd').onclick=()=>setTrim($('start').value, $('player').currentTime.toFixed(1));
$('rangeStart').oninput=e=>$('start').value=e.target.value;
$('rangeEnd').oninput=e=>$('end').value=e.target.value;
$('start').oninput=e=>$('rangeStart').value=e.target.value;
$('end').oninput=e=>$('rangeEnd').value=e.target.value;
$('analyze').onclick=async()=>{try{msg('analysisStatus','Analyzing...');const sourceId=videoId;const x=await api('/api/videos/'+sourceId+'/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clip_length:Number($('duration').value),count:Number($('count').value),transcribe:$('transcribe').checked})});if(sourceId!==videoId)return;msg('analysisStatus',x.warning||'Analysis complete — review suggestions before exporting');if(x.transcript?.length){transcript=x.transcript;drawCaptions();}const list=$('suggestions');list.replaceChildren();for(const s of (x.suggestions||x.clips||[])){const b=document.createElement('button');b.className='suggestion';b.textContent=(s.start||0).toFixed(1)+'–'+(s.end||0).toFixed(1)+'s';b.title=s.reason||'';b.onclick=()=>{setTrim(s.start,s.end);$('player').currentTime=s.start;};list.append(b)}}catch(e){msg('analysisStatus',e.message)}};
function drawCaptions(){const t=$('timelineTrack');t.querySelectorAll('.cue').forEach(x=>x.remove());transcript.forEach((c,i)=>{const b=document.createElement('button');b.className='cue';b.textContent=c.text;b.onclick=()=>{selected=i;$('captionEditor').classList.remove('hidden');$('cueText').value=c.text;$('cueStart').value=c.start;$('cueEnd').value=c.end};t.append(b)});msg('timelineStatus',transcript.length+' caption segments')};
$('generateCaptions').onclick=async()=>{try{msg('timelineStatus','Transcribing...');const sourceId=videoId;const x=await api('/api/videos/'+sourceId+'/transcribe',{method:'POST'});if(sourceId!==videoId)return;transcript=x.cues||x.segments||x.transcript||[];if(!Array.isArray(transcript))transcript=[];drawCaptions()}catch(e){msg('timelineStatus',e.message)}};
$('addCaption').onclick=()=>{transcript.push({start:Number($('start').value),end:Number($('end').value),text:'New caption'});drawCaptions()};
$('cueText').oninput=e=>{if(selected>=0)transcript[selected].text=e.target.value;drawCaptions()};
$('cueStart').onchange=e=>{if(selected>=0)transcript[selected].start=Number(e.target.value);drawCaptions()};
$('cueEnd').onchange=e=>{if(selected>=0)transcript[selected].end=Number(e.target.value);drawCaptions()};
$('deleteCaption').onclick=()=>{if(selected>=0)transcript.splice(selected,1);selected=-1;$('captionEditor').classList.add('hidden');drawCaptions()};
$('undoCaption').onclick=()=>msg('timelineStatus','Undo is not available in this build');
$('export').onclick=async()=>{try{msg('exportStatus','Starting render...');const body={start:Number($('start').value),end:Number($('end').value),aspect:$('aspect').value,subtitles:$('subtitles').checked,transcript:transcript};const sourceId=videoId;const x=await api('/api/videos/'+sourceId+'/export',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const job=x.job_id||x.job;for(let i=0;i<120;i++){await new Promise(r=>setTimeout(r,2000));const j=await api('/api/jobs/'+job);if(sourceId!==videoId)return;msg('exportStatus',j.status||'Processing');if(j.status==='done'||j.status==='completed'){offerDownload('download',j.url,'clipforge-export.mp4');if(j.srt_url)offerDownload('srtDownload',j.srt_url,'clipforge-captions.srt');msg('exportStatus','Ready to download');break}if(j.status==='error'||j.status==='failed')throw Error(j.error||'Render failed')}}catch(e){msg('exportStatus',e.message)}};
health();
