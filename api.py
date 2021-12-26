from flask import Flask, request
from flask_restful import Resource, Api, reqparse, abort, marshal, fields
from configparser import ConfigParser
import psycopg2 as pg
from psycopg2 import extensions
from healthcheck import HealthCheck, EnvironmentDump
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, generate_latest
from marshmallow import Schema, fields
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin

def create_app():
    app = Flask(__name__)
    api = Api(app)
    metrics = PrometheusMetrics(app)
    health = HealthCheck()
    envdump = EnvironmentDump()
    health.add_check(check_database_connection)
    envdump.add_section("application", application_data)
    app.add_url_rule("/healthcheck", "healthcheck", view_func=lambda: health.run())
    app.add_url_rule("/environment", "environment", view_func=lambda: envdump.run())
    api.add_resource(ListNarocnikov, "/narocniki")
    api.add_resource(Narocnik, "/narocniki/<int:id>")

    return app

def check_database_connection():
    conn = pg.connect('')
    if conn.poll() == extensions.POLL_OK:
        print ("POLL: POLL_OK")
    if conn.poll() == extensions.POLL_READ:
        print ("POLL: POLL_READ")
    if conn.poll() == extensions.POLL_WRITE:
        print ("POLL: POLL_WRITE")
    return True, "Database connection OK"

def application_data():
    return {"maintainer": "Teodor Janez Podobnik",
            "git_repo": "https://github.com/Paketi-org/Uporabniki.git"}

narocnikiPolja = {
    "id": fields.Integer,
    "ime": fields.String,
    "priimek": fields.String,
    "uporabnisko_ime": fields.String,
    "telefonska_stevilka": fields.String,
}

class NarocnikSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    priimek = fields.Str()
    uporabnisko_ime = fields.Str()
    telefonska_stevilka = fields.Str()
    atribut = fields.Str()
    vrednost = fields.Str()



class Narocnik(Resource):
    def __init__(self):
        self.table_name = 'narocniki'
        self.conn = pg.connect('')
        self.cur = self.conn.cursor()

        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int)
        self.parser.add_argument("ime", type=str)
        self.parser.add_argument("priimek", type=str)
        self.parser.add_argument("uporabnisko_ime", type=str)
        self.parser.add_argument("telefonska_stevilka", type=str)
        self.parser.add_argument("atribut", type=str)
        self.parser.add_argument("vrednost", type=str)

        super(Narocnik, self).__init__()

    def get(self, id):
        """
        Vrni podatke narocnika glede na ID
        """
        self.cur.execute("SELECT * FROM narocniki WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            abort(404)

        d = {}
        for el, k in zip(row[0], narocnikiPolja):
            d[k] = el

        return{"narocnik": marshal(d, narocnikiPolja)}, 200

    def put(self, id):
        """
        Posodobi podatke narocnika glede na ID
        """
        args = self.parser.parse_args()
        attribute = args["atribut"]
        value = args["vrednost"]
        self.cur.execute("""UPDATE {0} SET {1} = '{2}' WHERE id = {3}""".format(self.table_name, attribute, value, id))
        self.conn.commit()

        return 200

    def delete(self, id):
        """
        Izbriši narocnika glede na ID
        """
        self.cur.execute("SELECT * FROM narocniki")
        rows = self.cur.fetchall()
        ids = []
        for row in rows:
            ids.append(row[0])

        if id not in ids:
            abort(404)
        else:
            self.cur.execute("DELETE FROM narocniki WHERE id = %s" % str(id))
            self.conn.commit()

        return 200



class ListNarocnikov(Resource):
    def __init__(self):
        self.table_name = 'narocniki'
        self.conn = pg.connect('')
        self.cur = self.conn.cursor()
        self.cur.execute("select exists(select * from information_schema.tables where table_name=%s)", (self.table_name,))
        if self.cur.fetchone()[0]:
            print("Table {0} already exists".format(self.table_name))
        else:
            self.cur.execute('''CREATE TABLE narocniki (
                                id INT NOT NULL,
                                ime CHAR(10),
                                priimek CHAR(15),
                                uporabnisko_ime CHAR(10),
                                telefonska_stevilka CHAR(20)
                             )''')

        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int, required=True, help="ID naročnika je obvezen")
        self.parser.add_argument("ime", type=str, required=True, help="Ime naročnika je obvezen")
        self.parser.add_argument("priimek", type=str, required=True, help="Priimek naročnika je obvezen")
        self.parser.add_argument("uporabnisko_ime", type=str, required=True, help="Uporabniško ime naročnika je obvezen")
        self.parser.add_argument("telefonska_stevilka", type=str, help="Telefonska številka naročnika je obvezna")

    def get(self):
        """
        Vrni vse narocnike
        """
        self.cur.execute("SELECT * FROM narocniki")
        rows = self.cur.fetchall()
        ds = {}
        i = 0
        for row in rows:
            ds[i] = {}
            for el, k in zip(row, narocnikiPolja):
                ds[i][k] = el
            i += 1
            
        return{"narocniki": [marshal(d, narocnikiPolja) for d in ds.values()]}


    def post(self):
        """
        Dodaj novega narocnika
        """
        args = self.parser.parse_args()
        values = []
        for a in args.values():
            values.append(a)
        self.cur.execute('''INSERT INTO {0} (id, ime, priimek, uporabnisko_ime, telefonska_stevilka)
                VALUES ({1}, '{2}', '{3}', '{4}', '{5}')'''.format('narocniki', *values))
        self.conn.commit()
        narocnik = {
            "id": args["id"],
            "ime": args["ime"],
            "priimek": args["priimek"],
            "uporabnisko_ime": args["uporabnisko_ime"],
            "telefonska_stevika": args["telefonska_stevilka"],
        }

        return{"narocnik": marshal(narocnik, narocnikiPolja)}, 201


if __name__ == "__main__":
    app = create_app()

    @app.route("/random")
    def random_narocnik():
        """
        Nakljucna koncna tocka za narocnika
        ---
        get:
          description: Dobi nakljucnega narocnika
          responses:
            200:
              description: vrne narocnika
              content:
                application/json:
                  schema: NarocnikSchema
        """
        narocnik = {
            "id": 1,
            "ime": "Nika",
            "priimek": "Krasi",
            "uporabnisko_ime": "nk7220",
            "telefonska_stevika": "999999999999999999",
        }

        return NarocnikSchema().dump(narocnik)

    spec = APISpec(
        title="Narocniki Paketi-org",
        version="1.0.0",
        openapi_version="3.0.2",
        plugins=[FlaskPlugin(), MarshmallowPlugin()]
    )
    with app.test_request_context():
        spec.path(view=random_narocnik)
        print(spec.to_yaml())

    app.run(host="0.0.0.0", port=5003)
