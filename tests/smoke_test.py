import json, subprocess, tempfile, time, urllib.request, uuid
from pathlib import Path
BASE='http://127.0.0.1:8000'
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/'test.mp4'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i','testsrc2=size=320x240:rate=15','-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(p)],check=True)
    boundary='----clipforge'+uuid.uuid4().hex
    body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="test.mp4"\r\nContent-Type: video/mp4\r\n\r\n').encode()+p.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
    def call(path, payload=None, headers=None):
        req=urllib.request.Request(BASE+path,data=payload,headers=headers or {},method='POST' if payload is not None else 'GET')
        with urllib.request.urlopen(req,timeout=30) as r:return json.loads(r.read())
    u=call('/api/upload',body,{'Content-Type':f'multipart/form-data; boundary={boundary}'})
    print('Uploaded:',u['id'])
    a=call(f"/api/videos/{u['id']}/analyze",json.dumps({'clip_length':5,'count':2}).encode(),{'Content-Type':'application/json'})
    assert a['suggestions'];print('Suggestions:',len(a['suggestions']))
    j=call(f"/api/videos/{u['id']}/export",json.dumps({'start':0,'end':3,'aspect':'9:16'}).encode(),{'Content-Type':'application/json'})
    for _ in range(40):
        time.sleep(1)
        state=call('/api/jobs/'+j['job_id'])
        if state['status']=='done':break
        if state['status']=='error':raise RuntimeError(state['error'])
    assert state['status']=='done',state
    with urllib.request.urlopen(BASE+state['url']) as r:assert r.read(16)
    print('PASS: upload, analyze, render and download')
