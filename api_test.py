import unittest
import requests
from api import create_app
import json

class TestAPI(unittest.TestCase):
    app = create_app()

    def setUp(self):
        self.BASE = "http://172.27.1.3:5000/"
        self.maxDiff = None

    def test_post_narocniki(self):
        resp = requests.post(self.BASE + "/narocniki", {"id": 3, "ime": "Nikolina", "priimek": "Kraševka", "uporabnisko_ime": "nk_fuzine", "telefonska_stevilka": "999999999"})
        self.assertEqual(resp.status_code, 201)

    def test_put_narocniki(self):
        resp = requests.put(self.BASE + "/narocniki/3", {"atribut": "ime", "vrednost": "Teolina"})
        self.assertEqual(resp.status_code, 200)

    def test_delete_narocnik(self):
        resp = requests.delete(self.BASE + "/narocniki/3")
        self.assertEqual(resp.status_code, 200)

    def test_healthcheck(self):
        resp = requests.get(self.BASE + "/healthcheck")
        self.assertIsNotNone(resp)

    def test_env(self):
        resp = requests.get(self.BASE + "/environment")
        self.assertIsNotNone(resp)

if __name__ == '__main__':
    unittest.main()
