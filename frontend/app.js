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
        const status = await api('/api/health');
        await api('/api/access');
        msg('server', status.ffmpeg ? 'Engine online' : 'FFmpeg unavailable');
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
let checkedYouTubeUrl = '', objectUrl = '';
const editorActions = ['analyze', 'generateCaptions', 'addCaption', 'export'];
const jsonHeaders = {'Content-Type': 'application/json'};

function resetYouTubeLink() {
    checkedYouTubeUrl = '';
    $('youtubeSteps').classList.add('hidden');
    $('youtubeStudio').removeAttribute('href');
    $('youtubeAuthorized').checked = false;
    $('youtubeFile').disabled = true;
    msg('youtubeStatus', '');
}

$('youtubeUrl').oninput = resetYouTubeLink;
$('youtubeForm').onsubmit = async event => {
    event.preventDefault();
    resetYouTubeLink();
    const url = $('youtubeUrl').value.trim();
    $('checkYouTube').disabled = true;
    msg('youtubeStatus', 'Checking link…');
    try {
        const result = await api('/api/import/youtube/validate', {
            method: 'POST', headers: jsonHeaders, body: JSON.stringify({url})
        });
        if (url !== $('youtubeUrl').value.trim()) return;
        checkedYouTubeUrl = url;
        $('youtubeStudio').href = result.studio_url;
        $('youtubeSteps').classList.remove('hidden');
        msg('youtubeStatus', 'Link format is valid. Save your video in YouTube Studio to continue.');
    } catch (error) {
        if (url === $('youtubeUrl').value.trim()) msg('youtubeStatus', error.message);
    } finally {
        $('checkYouTube').disabled = false;
    }
};
$('youtubeAuthorized').onchange = () => {
    $('youtubeFile').disabled = !$('youtubeAuthorized').checked;
};

async function uploadVideo(input, youtubeUrl = '') {
    const file = input.files[0];
    if (!file) return;
    const previous = editorActions.map(id => $(id).disabled);
    const locked = [...editorActions, 'file', 'youtubeFile', 'youtubeUrl', 'youtubeAuthorized', 'saveBackend'];
    for (const id of locked) $(id).disabled = true;
    let ready = false;
    try {
        msg('uploadStatus', 'Uploading ' + file.name + '…');
        const form = new FormData();
        form.append('file', file);
        if (youtubeUrl) {
            form.append('youtube_url', youtubeUrl);
            form.append('authorized', 'true');
        }
        const video = await api('/api/upload', {method: 'POST', body: form});
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
        objectUrl = URL.createObjectURL(file);
        $('player').src = objectUrl;
        $('placeholder').style.display = 'none';
        msg('meta', file.name);
        msg('uploadStatus', 'Video ready');
        ready = true;
    } catch (error) {
        msg('uploadStatus', error.message);
    } finally {
        input.value = '';
        for (const id of locked) $(id).disabled = false;
        $('youtubeFile').disabled = !$('youtubeAuthorized').checked;
        editorActions.forEach((id, index) => { $(id).disabled = !ready && previous[index]; });
    }
}

$('file').onchange = event => uploadVideo(event.target);
$('youtubeFile').onchange = event => {
    if (checkedYouTubeUrl && $('youtubeAuthorized').checked) {
        return uploadVideo(event.target, checkedYouTubeUrl);
    }
};
$('markStart').onclick=()=>{$('start').value=$('player').currentTime.toFixed(1)};
$('markEnd').onclick=()=>{$('end').value=$('player').currentTime.toFixed(1)};
$('rangeStart').oninput=e=>$('start').value=e.target.value;
$('rangeEnd').oninput=e=>$('end').value=e.target.value;
$('start').oninput=e=>$('rangeStart').value=e.target.value;
$('end').oninput=e=>$('rangeEnd').value=e.target.value;
$('analyze').onclick=async()=>{try{msg('analysisStatus','Analyzing...');const sourceId=videoId;const x=await api('/api/videos/'+sourceId+'/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clip_length:Number($('duration').value),count:Number($('count').value),transcribe:$('transcribe').checked})});if(sourceId!==videoId)return;msg('analysisStatus',x.warning||'Analysis complete');const list=$('suggestions');list.replaceChildren();for(const s of (x.suggestions||x.clips||[])){const b=document.createElement('button');b.textContent=(s.start||0).toFixed(1)+'–'+(s.end||0).toFixed(1)+'s';b.onclick=()=>{$('start').value=s.start;$('end').value=s.end};list.append(b)}}catch(e){msg('analysisStatus',e.message)}};
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
