import requests

BASE = "http://172.27.1.3:5000/"

r1 = requests.get(BASE + "/narocniki")
print(r1.json())

r4 = requests.post(BASE + "/narocniki", {"id": 3, "ime": "Nikolina", "priimek": "Kraševka", "uporabnisko_ime": "nk_fuzine", "telefonska_stevilka": "999999999"})
#print(r4.json())

r3 = requests.get(BASE + "/narocniki")
print(r3.json())

r4 = requests.delete(BASE + "/narocniki/3")
#print(r4.json())

r3 = requests.get(BASE + "/narocniki")
print(r3.json())

r4 = requests.post(BASE + "/narocniki", {"id": 3, "ime": "Nikolina", "priimek": "Kraševka", "uporabnisko_ime": "nk_fuzine", "telefonska_stevilka": "999999999"})
r4 = requests.post(BASE + "/narocniki", {"id": 4, "ime": "Teolina", "priimek": "Podobnikica", "uporabnisko_ime": "nk_kamnik", "telefonska_stevilka": "11111111"})

r3 = requests.get(BASE + "/narocniki")
print(r3.json())

r4 = requests.delete(BASE + "/narocniki/3")

r3 = requests.get(BASE + "/narocniki")
print(r3.json())

r6 = requests.get(BASE + "/narocniki/4")
print(r6.json())

r6 = requests.get(BASE + "/healthcheck")
