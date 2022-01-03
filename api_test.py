import unittest
import requests
import json

class TestAPI(unittest.TestCase):

    def setUp(self):
        self.BASE = "http://localhost:5003/"
        self.maxDiff = None

    def test_1_post_narocniki(self):
        resp = requests.post(self.BASE + "/narocniki", {"id": 3, "ime": "Nikolina", "priimek": "Kraševka", "uporabnisko_ime": "nk_fuzine", "telefonska_stevilka": "999999999"})
        self.assertEqual(resp.status_code, 201)

    def test_2_put_narocniki(self):
        resp = requests.put(self.BASE + "/narocniki/3", {"atribut": "ime", "vrednost": "Teolina"})
        self.assertEqual(resp.status_code, 200)

    def test_3_delete_narocnik(self):
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
