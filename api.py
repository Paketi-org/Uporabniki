from flask import Flask
from flask_restx import Resource, Api, fields, reqparse, abort, marshal, marshal_with
from configparser import ConfigParser
import psycopg2 as pg
from psycopg2 import extensions
from healthcheck import HealthCheck, EnvironmentDump
from prometheus_flask_exporter import PrometheusMetrics
from prometheus_client import Counter, generate_latest

# TODO: Put version in config file

app = Flask(__name__)
api = Api(app, version='1.0', title='Narocniki API', description='Abstrakt Narocniki API',default_swagger_filename='openapi.json', default='Uporabniki CRUD', default_label='koncne tocke in operacije')
narocnikApiModel = api.model('ModelNarocnika', {
    "id": fields.Integer(readonly=True, description='ID narocnika'),
    "ime": fields.String(readonly=True, description='Ime narocnika'),
    "priimek": fields.String(readonly=True, description='Priimek narocnika'),
    "uporabnisko_ime": fields.String(readonly=True, description='Uporabnisko ime narocnika'),
    "telefonska_stevilka": fields.String(readonly=True, description='Telefonska stevilka narocnika')
})
narocnikiApiModel = api.model('ModelNarocnikov', {"narocniki": fields.List(fields.Nested(narocnikApiModel))})
ns = api.namespace('Uporabniki CRUD', description='Uporabniki koncne tocke in operacije')
posodobiModel = api.model('PosodobiNarocnika', {
    "atribut": fields.String,
    "vrednost": fields.String
})

def create_app():
    metrics = PrometheusMetrics(app)
    health = HealthCheck()
    envdump = EnvironmentDump()
    health.add_check(check_database_connection)
    envdump.add_section("application", application_data)
    app.add_url_rule("/healthcheck", "healthcheck", view_func=lambda: health.run())
    app.add_url_rule("/environment", "environment", view_func=lambda: envdump.run())
    api.add_resource(ListNarocnikov, "/narocniki")
    api.add_resource(Narocnik, "/narocniki/<int:id>")

class NarocnikModel:
    def __init__(self, id, ime, priimek, uporabnisko_ime, telefonska_stevilka):
        self.id = id
        self.ime = ime
        self.priimek = priimek
        self.uporabnisko_ime = uporabnisko_ime
        self.telefonska_stevilka = telefonska_stevilka

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

class Narocnik(Resource):
    def __init__(self, *args, **kwargs):
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

        super(Narocnik, self).__init__(*args, **kwargs)

    @marshal_with(narocnikApiModel)
    @ns.response(404, 'Narocnik ni najden')
    @ns.doc("Vrni narocnika")
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
                ime = d["ime"].strip(),
                priimek = d["priimek"].strip(),
                uporabnisko_ime = d["uporabnisko_ime"].strip(),
                telefonska_stevilka = d["telefonska_stevilka"].strip())

        return narocnik, 200

    @marshal_with(narocnikApiModel)
    @ns.expect(posodobiModel)
    @ns.response(404, 'Narocnik ni najden')
    @ns.doc("Posodobi narocnika")
    def put(self, id):
        """
        Posodobi podatke narocnika glede na ID
        """
        self.cur.execute("SELECT * FROM narocniki WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            abort(404)

        args = self.parser.parse_args()
        attribute = args["atribut"]
        value = args["vrednost"]
        self.cur.execute("""UPDATE {0} SET {1} = '{2}' WHERE id = {3}""".format(self.table_name, attribute, value, id))
        self.conn.commit()

        d = {}
        for el, k in zip(row[0], narocnikiPolja):
            d[k] = el

        narocnik = NarocnikModel(
                id = d["id"],
                ime = d["ime"].strip(),
                priimek = d["priimek"].strip(),
                uporabnisko_ime = d["uporabnisko_ime"].strip(),
                telefonska_stevilka = d["telefonska_stevilka"].strip())

        return narocnik, 200

    @ns.doc("Izbrisi narocnika")
    @ns.response(404, 'Narocnik ni najden')
    @ns.response(204, 'Narocnik izbrisan')
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

        return 204

class ListNarocnikov(Resource):
    def __init__(self, *args, **kwargs):
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

        super(ListNarocnikov, self).__init__(*args, **kwargs)

    @ns.marshal_list_with(narocnikiApiModel)
    @ns.doc("Vrni vse narocnike")
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

        narocniki = []
        for d in ds:
            narocnik = NarocnikModel(
                    id = ds[d]["id"],
                    ime = ds[d]["ime"].strip(),
                    priimek = ds[d]["priimek"].strip(),
                    uporabnisko_ime = ds[d]["uporabnisko_ime"].strip(),
                    telefonska_stevilka = ds[d]["telefonska_stevilka"].strip())
            narocniki.append(narocnik)
            
        return {"narocniki": narocniki}, 200 

    @marshal_with(narocnikApiModel)
    @ns.expect(narocnikApiModel)
    @ns.doc("Dodaj narocnika")
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
                ime = args["ime"].strip(),
                priimek = args["priimek"].strip(),
                uporabnisko_ime = args["uporabnisko_ime"].strip(),
                telefonska_stevilka = args["telefonska_stevilka"].strip())

        return narocnik, 201


if __name__ == "__main__":
    create_app()
    app.run(host="0.0.0.0", port=5003)
