import io
import json
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
from local_api import create_app, configured_origins


def fake_runner(folder, fields, register):
    output = folder / 'result'
    output.mkdir()
    Image.new('RGB', (128,188), 'gray').save(output/'illustration.png')
    (output/'metrics.json').write_text(json.dumps({'status':'success','changed_pixels_outside_mask':0}))

class ApiTests(unittest.TestCase):
    def test_phone_origin_is_explicit_and_other_origins_are_rejected(self):
        origin = 'http://192.168.1.20:5175'
        self.assertNotIn(origin, configured_origins(''))
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {'REST_PREVIEW_ORIGINS': origin}):
            with TestClient(create_app(directory, fake_runner)) as client:
                self.assertEqual(client.post('/session', headers={'Origin': origin}).status_code, 200)
                self.assertEqual(client.post('/session', headers={'Origin': 'http://192.168.1.21:5175'}).status_code, 403)
                self.assertEqual(client.post('/session', headers={'Origin': 'https://evil.example'}).status_code, 403)
        # Some Wi-Fi networks assign globally routable addresses; explicit opt-in is still required.
        public_origin = 'http://104.39.139.24:5175'
        self.assertNotIn(public_origin, configured_origins(''))
        self.assertIn(public_origin, configured_origins(public_origin))
        for invalid in ['*', 'https://evil.example:443', 'http://0.0.0.0:5175', 'http://224.0.0.1:5175', origin + '/path']:
            with self.assertRaises(ValueError): configured_origins(invalid)

    def test_upload_ownership_and_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            with TestClient(create_app(directory, fake_runner)) as client:
                self.assertEqual(client.post('/session').status_code,200)
                raw=io.BytesIO(); Image.new('RGB',(128,128)).save(raw,format='PNG')
                fields={'consent':'true','face_box':'[0,0,128,128]','edit_box':'[20,20,40,40]', 'product':'Example product'}
                def submit(data):
                    return client.post('/jobs',data=data,files={'reference':('image.png',raw.getvalue(),'image/png')})
                self.assertEqual(submit({**fields,'consent':'false'}).status_code,400)
                self.assertEqual(submit({**fields,'edit_box':'[120,120,150,150]'}).status_code,400)
                response=submit(fields); self.assertEqual(response.status_code,202,response.text)
                key=response.json()['id']
                for _ in range(100):
                    status=client.get('/jobs/'+key).json()
                    if status['status']=='completed': break
                    time.sleep(.01)
                self.assertEqual(status['status'],'completed')
                self.assertEqual(status['productNote'],'Example product')
                self.assertNotIn('progress', status)
                self.assertEqual(client.get('/jobs/'+key+'/image').status_code,200)
                cookie=client.cookies.get('rest_illustration_session'); client.cookies.clear()
                client.post('/session')
                self.assertEqual(client.get('/jobs/'+key).status_code,404)
                self.assertEqual(client.delete('/jobs/'+key).status_code,404)
                client.cookies.clear(); client.cookies.set('rest_illustration_session',cookie)
                self.assertEqual(client.delete('/jobs/'+key).status_code,204)
                self.assertFalse((Path(directory)/key).exists())
                self.assertEqual(client.post('/session',headers={'Origin':'https://evil.example'}).status_code,403)

if __name__=='__main__': unittest.main()
