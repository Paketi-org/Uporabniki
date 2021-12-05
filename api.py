from flask import Flask
from flask_restful import Resource, Api, reqparse, abort, marshal, fields

app = Flask(__name__)
api = Api(app)

uporabniki = [{
    "id": 1,
    "ime": "Peter",
    "priimek": "Skala",
    "uporabnisko_ime": "ps4348",
},
    {
    "id": 2,
    "ime": "Tim",
    "priimek": "Melan",
    "uporabnisko_ime": "tm1318",
}
]

uporabnikiFields = {
    "id": fields.Integer,
    "ime": fields.String,
    "priimek": fields.String,
    "uporabnisko_ime": fields.String,
}

class Uporabnik(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument("ime", type=str, location="json")
        self.reqparse.add_argument("priimek", type=str, location="json")
        self.reqparse.add_argument("uporabnisko_ime", type=str, location="json")

        super(Uporabnik, self).__init__()

    def get(self, id):
        uporabnik = [uporabnik for uporabnik in uporabniki if uporabnik['id'] == id]

        if(len(uporabnik) == 0):
            abort(404)

        return{"uporabnik": marshal(uporabnik[0], uporabnikiFields)}

    def put(self, id):
        uporabnik = [uporabnik for uporabnik in uporabniki if uporabnik['id'] == id]

        if len(uporabnik) == 0:
            abort(404)

        uporabnik = uporabnik[0]

        args = self.reqparse.parse_args()
        for k, v in args.items():
            # Check if the passed value is not null
            if v is not None:
                # if not, set the element in the books dict with the 'k' object to the value provided in the request.
                uporabnik[k] = v

        return{"uporabnik": marshal(uporabnik, uporabnikFields)}

    def delete(self, id):
        uporabnik = [uporabnik for uporabnik in uporabniki if uporabnik['id'] == id]

        if(len(uporabnik) == 0):
            abort(404)

        uporabniki.remove(uporabnik[0])

        return 201


class ListUporabnikov(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument(
            "ime", type=str, required=True, help="Ime uporabnika", location="json")
        self.reqparse.add_argument(
            "priimek", type=str, required=True, help="Priimek uporabnika", location="json")
        self.reqparse.add_argument(
            "uporabnisko_ime", type=str, required=True, help="Uporabnisko ime uporabnika", location="json")

    def get(self):
        return{"uporabniki": [marshal(uporabnik, uporabnikiFields) for uporabnik in uporabniki]}

    def post(self):
        args = self.reqparse.parse_args()
        uporabnik = {
            "id": uporabniki[-1]['id'] + 1 if len(uporabniki) > 0 else 1,
            "ime": args["ime"],
            "priimek": args["priimek"],
            "uporabnisko_ime": args["uporabnisko_ime"],
        }

        uporabniki.append(uporabnik)
        return{"uporabnik": marshal(uporabnik, uporabnikiFields)}, 201


api.add_resource(ListUporabnikov, "/uporabniki")
api.add_resource(Uporabnik, "/uporabniki/<int:id>")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
