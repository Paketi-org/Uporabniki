from flask import Flask, request
from flask_restful import Resource, Api, reqparse, abort, marshal, fields
from configparser import ConfigParser
import psycopg2 as pg
from psycopg2 import extensions
from healthcheck import HealthCheck, EnvironmentDump
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, generate_latest
from apispec.ext.marshmallow import MarshmallowPlugin
from flask_apispec import marshal_with, FlaskApiSpec
from flask_apispec.views import MethodResource
from marshmallow import Schema, fields
from apispec import APISpec

def create_app():
    app = Flask(__name__)
    app.config.update({
        'APISPEC_SPEC': APISpec(
            openapi_version="3.0.2",
            title='narocniki',
            version='v1',
            plugins=[MarshmallowPlugin()],
        ),
        'APISPEC_SWAGGER_URL': '/swagger/',
    })
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
    docs = FlaskApiSpec(app)
    docs.register(ListNarocnikov)
    docs.register(Narocnik)

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

class NarocnikModel:
    def __init__(self, id, ime, priimek, uporabnisko_ime, telefonska_stevilka):
        self.id = id
        self.ime = ime
        self.priimek = priimek
        self.uporabnisko_ime = uporabnisko_ime
        self.telefonska_stevilka = telefonska_stevilka

class NarocnikSchema(Schema):
    id = fields.Integer()
    ime = fields.String()
    priimek = fields.String()
    uporabnisko_ime = fields.String()
    telefonska_stevilka = fields.String()

class Narocnik(MethodResource):
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

    @marshal_with(NarocnikSchema)
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

        narocnik = NarocnikModel(
                id = d["id"],
                ime = d["ime"],
                priimek = d["priimek"],
                uporabnisko_ime = d["uporabnisko_ime"],
                telefonska_stevilka = d["telefonska_stevilka"])

        return narocnik, 200

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



class ListNarocnikov(MethodResource):
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

    @marshal_with(NarocnikSchema)
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
        narocnik = NarocnikModel(
                id = args["id"],
                ime = args["ime"],
                priimek = args["priimek"],
                uporabnisko_ime = args["uporabnisko_ime"],
                telefonska_stevilka = args["telefonska_stevilka"])

        return narocnik, 201


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5003)
