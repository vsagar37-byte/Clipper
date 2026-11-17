import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend import main


class YouTubeImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = patch.object(main, 'DATA', Path(self.tmp.name))
        self.data.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.data.stop()
        self.tmp.cleanup()

    def test_reject_arbitrary_urls(self):
        for url in ['https://127.0.0.1/video', 'https://youtube.com.evil.test/watch?v=m5vKYMhZ9CM',
                    'https://user:pass@youtube.com/watch?v=m5vKYMhZ9CM',
                    'https://youtube.com/playlist?list=123']:
            self.assertEqual(self.client.post('/api/import/youtube', json={'url': url}).status_code, 400)

    def test_import_feeds_editor(self):
        def download(vid, folder, *args):
            self.assertEqual(vid, 'm5vKYMhZ9CM')
            (folder / 'source.mp4').write_bytes(b'fixture')
            return {'title': 'Test video', 'youtube_video_id': vid}
        with patch('backend.youtube_import.download_youtube', side_effect=download), patch.object(
            main, 'probe', return_value={'duration': 1860, 'width': 1280, 'height': 720, 'has_audio': True}):
            response = self.client.post('/api/import/youtube', json={'url': 'https://youtu.be/m5vKYMhZ9CM?si=test'})
        self.assertEqual(response.status_code, 202)
        state = self.client.get('/api/jobs/' + response.json()['job_id']).json()
        self.assertEqual(state['status'], 'done')
        self.assertEqual(state['video']['duration'], 1860)
        self.assertEqual(self.client.get(state['video']['video_url']).content, b'fixture')
        self.assertTrue((main.DATA / state['video']['id'] / 'meta.json').exists())

    def test_failure_cleans_up_and_releases_slot(self):
        with patch('backend.youtube_import.download_youtube', side_effect=ValueError('YouTube blocked this server')):
            response = self.client.post('/api/import/youtube', json={'url': 'https://youtu.be/m5vKYMhZ9CM'})
        state = self.client.get('/api/jobs/' + response.json()['job_id']).json()
        self.assertEqual(state['status'], 'error')
        self.assertEqual(list(main.DATA.iterdir()), [])
        self.assertTrue(main.IMPORT_SLOT.acquire(blocking=False))
        main.IMPORT_SLOT.release()

    def test_concurrency_limit(self):
        main.IMPORT_SLOT.acquire()
        try:
            self.assertEqual(self.client.post('/api/import/youtube', json={'url': 'https://youtu.be/m5vKYMhZ9CM'}).status_code, 429)
        finally:
            main.IMPORT_SLOT.release()

    def test_auth_required(self):
        with patch.dict('os.environ', {'CLIPFORGE_ACCESS_KEY': 'x'*32}):
            self.assertEqual(self.client.post('/api/import/youtube', json={'url': 'https://youtu.be/m5vKYMhZ9CM'}).status_code, 401)


if __name__ == '__main__':
    unittest.main()
