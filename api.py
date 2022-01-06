from flask import Flask, request
from flask_restx import Resource, Api, fields, reqparse, abort, marshal, marshal_with
from configparser import ConfigParser
import psycopg2 as pg
from psycopg2 import extensions
from healthcheck import HealthCheck, EnvironmentDump
from prometheus_flask_exporter import PrometheusMetrics, RESTfulPrometheusMetrics
from prometheus_client import Counter, generate_latest
from fluent import sender, handler
import logging
from time import time
import json
import os
import subprocess
import socket
import random

app = Flask(__name__)

# Load configurations from the config file
def load_configurations():
    app.config.from_file("config.json", load=json.load)

    with open("config.json") as json_file:
        data = json.load(json_file)
        # Override variables defined in the config file with the ones defined in the environment(if set)
        for item in data:
            if os.environ.get(item):
                app.config[item] = os.environ.get(item)


load_configurations()


@app.route("/")
def welcome():
    return "Welcome!"


custom_format = {
    "name": "%(name_of_service)s",
    "method": "%(crud_method)s",
    "traffic": "%(directions)s",
    "ip": "%(ip_node)s",
    "status": "%(status)s",
    "code": "%(http_code)s",
}
logging.basicConfig(level=logging.INFO)
l = logging.getLogger("Uporabniki")
h = handler.FluentHandler(
    "Uporabniki", host=app.config["FLUENT_IP"], port=int(app.config["FLUENT_PORT"])
)
formatter = handler.FluentRecordFormatter(custom_format)
h.setFormatter(formatter)
l.addHandler(h)

l.info(
    "Setting up Uporabniki App",
    extra={
        "name_of_service": "Uporabniki",
        "crud_method": None,
        "directions": None,
        "ip_node": None,
        "status": None,
        "http_code": None,
    },
)

api = Api(
    app,
    version="1.0",
    doc="/narocniki/openapi",
    title="Narocniki API",
    description="Abstrakt Narocniki API",
    default_swagger_filename="openapi.json",
    default="Uporabniki CRUD",
    default_label="koncne tocke in operacije",
)
narocnikApiModel = api.model(
    "ModelNarocnika",
    {
        "id": fields.Integer(readonly=True, description="ID narocnika"),
        "ime": fields.String(readonly=True, description="Ime narocnika"),
        "priimek": fields.String(readonly=True, description="Priimek narocnika"),
        "ocena": fields.String(readonly=True, description="Ocena narocnika"),
        "uporabnisko_ime": fields.String(
            readonly=True, description="Uporabnisko ime narocnika"
        ),
        "telefonska_stevilka": fields.String(
            readonly=True, description="Telefonska stevilka narocnika"
        ),
    },
)
narocnikiApiModel = api.model(
    "ModelNarocnikov", {"narocniki": fields.List(fields.Nested(narocnikApiModel))}
)
ocenaApiModel = api.model(
    "OcenaNarocnika",
    {
        "id": fields.Integer(readonly=True, description="ID narocnika"),
        "ime": fields.String(readonly=True, description="Ime narocnika"),
        "priimek": fields.String(readonly=True, description="Priimek narocnika"),
        "ocena": fields.String(readonly=True, description="Ocena narocnika"),
        "mesto": fields.String(readonly=True, description="Mesto narocnika"),
    },
)
oceneApiModel = api.model(
    "LestvicaNarocnikov", {"narocniki": fields.List(fields.Nested(ocenaApiModel))}
)
nagradaApiModel = api.model(
    "NagradaNarocnika",
    {
        "id": fields.Integer(readonly=True, description="ID narocnika"),
        "ime": fields.String(readonly=True, description="Ime narocnika"),
        "priimek": fields.String(readonly=True, description="Priimek narocnika"),
        "nagrada": fields.String(readonly=True, description="Nagrada narocnika"),
    },
)
ns = api.namespace(
    "Uporabniki CRUD", description="Uporabniki koncne tocke in operacije"
)
posodobiModel = api.model(
    "PosodobiNarocnika", {"atribut": fields.String, "vrednost": fields.String}
)

metrics = RESTfulPrometheusMetrics(app, api)
by_path_counter = metrics.counter(
    "by_path_counter",
    "Request count by request paths",
    labels={"path": lambda: request.path},
)


def connect_to_database():
    return pg.connect(
        database=app.config["PGDATABASE"],
        user=app.config["PGUSER"],
        password=app.config["PGPASSWORD"],
        port=app.config["DATABASE_PORT"],
        host=app.config["DATABASE_IP"],
        connect_timeout=3,
    )


# Kubernetes Liveness Probe (200-399 healthy, 400-599 sick)
def check_database_connection():
    conn = connect_to_database()
    if conn.poll() == extensions.POLL_OK:
        print("POLL: POLL_OK")
    if conn.poll() == extensions.POLL_READ:
        print("POLL: POLL_READ")
    if conn.poll() == extensions.POLL_WRITE:
        print("POLL: POLL_WRITE")
    l.info(
        "Healtcheck povezave z bazo",
        extra={
            "name_of_service": "Uporabniki",
            "crud_method": "healthcheck",
            "directions": "out",
            "ip_node": socket.gethostbyname(socket.gethostname()),
            "status": "success",
            "http_code": None,
        },
    )
    return True, "Database connection OK"


def application_data():
    l.info(
        "Application environmental data dump",
        extra={
            "name_of_service": "Uporabniki",
            "crud_method": "envdump",
            "directions": "out",
            "ip_node": socket.gethostbyname(socket.gethostname()),
            "status": "success",
            "http_code": None,
        },
    )
    return {
        "maintainer": "Teodor Janez Podobnik",
        "git_repo": "https://github.com/Paketi-org/Uporabniki.git",
    }


class NarocnikModel:
    def __init__(self, id, ime, priimek, ocena, uporabnisko_ime, telefonska_stevilka):
        self.id = id
        self.ime = ime
        self.priimek = priimek
        self.ocena = ocena
        self.uporabnisko_ime = uporabnisko_ime
        self.telefonska_stevilka = telefonska_stevilka


class OcenaModel:
    def __init__(self, id, ime, priimek, ocena, mesto):
        self.id = id
        self.ime = ime
        self.priimek = priimek
        self.ocena = ocena
        self.mesto = mesto


class NagradaModel:
    def __init__(self, id, ime, priimek, nagrada):
        self.id = id
        self.ime = ime
        self.priimek = priimek
        self.nagrada = nagrada


narocnikiPolja = {
    "id": fields.Integer,
    "ime": fields.String,
    "priimek": fields.String,
    "ocena": fields.String,
    "uporabnisko_ime": fields.String,
    "telefonska_stevilka": fields.String,
}


class Narocnik(Resource):
    def __init__(self, *args, **kwargs):
        self.table_name = "narocniki"
        self.conn = connect_to_database()
        self.cur = self.conn.cursor()
        if self.cur.fetchone()[0]:
            print("Table {0} already exists".format(self.table_name))
        else:
            self.cur.execute(
                """CREATE TABLE narocniki (
                                id INT NOT NULL,
                                ime CHAR(20),
                                priimek CHAR(20),
                                ocena CHAR(20),
                                uporabnisko_ime CHAR(20),
                                telefonska_stevilka CHAR(20)
                             )"""
            )

        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int)
        self.parser.add_argument("ime", type=str)
        self.parser.add_argument("priimek", type=str)
        self.parser.add_argument("ocena", type=str)
        self.parser.add_argument("uporabnisko_ime", type=str)
        self.parser.add_argument("telefonska_stevilka", type=str)
        self.parser.add_argument("atribut", type=str)
        self.parser.add_argument("vrednost", type=str)

        super(Narocnik, self).__init__(*args, **kwargs)

    @by_path_counter
    @marshal_with(narocnikApiModel)
    @ns.response(404, "Narocnik ni najden")
    @ns.doc("Vrni narocnika")
    def get(self, id):
        """
        Vrni podatke narocnika glede na ID
        """
        l.info(
            "Zahtevaj narocnika z ID %s" % str(id),
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "get",
                "directions": "in",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": None,
                "http_code": None,
            },
        )
        self.cur.execute("SELECT * FROM narocniki WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if len(row) == 0:
            l.warning(
                "Narocnik z ID %s ni bil najden in ne bo izbrisan" % str(id),
                extra={
                    "name_of_service": "Uporabniki",
                    "crud_method": "get",
                    "directions": "out",
                    "ip_node": socket.gethostbyname(socket.gethostname()),
                    "status": "fail",
                    "http_code": 404,
                },
            )
            abort(404)

        d = {}
        for el, k in zip(row[0], narocnikiPolja):
            d[k] = el

        narocnik = NarocnikModel(
            id=d["id"],
            ime=d["ime"].strip(),
            priimek=d["priimek"].strip(),
            ocena=d["ocena"].strip(),
            uporabnisko_ime=d["uporabnisko_ime"].strip(),
            telefonska_stevilka=d["telefonska_stevilka"].strip(),
        )

        l.info(
            "Vrni narocnika z ID %s" % str(id),
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "get",
                "directions": "out",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": "success",
                "http_code": 200,
            },
        )

        return narocnik, 200

    @marshal_with(narocnikApiModel)
    @ns.expect(posodobiModel)
    @ns.response(404, "Narocnik ni najden")
    @ns.doc("Posodobi narocnika")
    def put(self, id):
        """
        Posodobi podatke narocnika glede na ID
        """
        l.info(
            "Posodobi narocnika z ID %s" % str(id),
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "put",
                "directions": "in",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": None,
                "http_code": None,
            },
        )
        self.cur.execute("SELECT * FROM narocniki WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if len(row) == 0:
            l.warning(
                "Narocnik z ID %s ne obstaja" % str(id),
                extra={
                    "name_of_service": "Uporabniki",
                    "crud_method": "put",
                    "directions": "out",
                    "ip_node": socket.gethostbyname(socket.gethostname()),
                    "status": "fail",
                    "http_code": 404,
                },
            )
            abort(404)

        args = self.parser.parse_args()
        attribute = args["atribut"]
        value = args["vrednost"]
        self.cur.execute(
            """UPDATE {0} SET {1} = '{2}' WHERE id = {3}""".format(
                self.table_name, attribute, value, id
            )
        )
        self.conn.commit()

        d = {}
        for el, k in zip(row[0], narocnikiPolja):
            d[k] = el

        narocnik = NarocnikModel(
            id=d["id"],
            ime=d["ime"].strip(),
            priimek=d["priimek"].strip(),
            ocena=d["ocena"].strip(),
            uporabnisko_ime=d["uporabnisko_ime"].strip(),
            telefonska_stevilka=d["telefonska_stevilka"].strip(),
        )

        l.info(
            "Vrni posodobljenega narocnika z ID %s" % str(id),
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "put",
                "directions": "out",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": "success",
                "http_code": 200,
            },
        )

        return narocnik, 200

    @ns.doc("Izbrisi narocnika")
    @ns.response(404, "Narocnik ni najden")
    @ns.response(204, "Narocnik izbrisan")
    def delete(self, id):
        """
        Izbriši narocnika glede na ID
        """
        l.info(
            "Izbrisi narocnika z ID %s" % str(id),
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "delete",
                "directions": "in",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": None,
                "http_code": None,
            },
        )
        self.cur.execute("SELECT * FROM narocniki")
        rows = self.cur.fetchall()
        ids = []
        for row in rows:
            ids.append(row[0])

        if id not in ids:
            l.warning(
                "Narocnik z ID %s ni bil najden in ne bo izbrisan" % str(id),
                extra={
                    "name_of_service": "Uporabniki",
                    "crud_method": "delete",
                    "directions": "out",
                    "ip_node": socket.gethostbyname(socket.gethostname()),
                    "status": "fail",
                    "http_code": 404,
                },
            )
            abort(404)
        else:
            self.cur.execute("DELETE FROM narocniki WHERE id = %s" % str(id))
            self.conn.commit()

        l.info(
            "Narocnik z ID %s izbrisan" % str(id),
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "delete",
                "directions": "out",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": "success",
                "http_code": 204,
            },
        )

        return 204


class ListNarocnikov(Resource):
    def __init__(self, *args, **kwargs):
        self.table_name = "narocniki"
        self.conn = connect_to_database()
        self.cur = self.conn.cursor()
        self.cur.execute(
            "select exists(select * from information_schema.tables where table_name=%s)",
            (self.table_name,),
        )
        if self.cur.fetchone()[0]:
            print("Table {0} already exists".format(self.table_name))
        else:
            self.cur.execute(
                """CREATE TABLE narocniki (
                                id INT NOT NULL,
                                ime CHAR(20),
                                priimek CHAR(20),
                                ocena CHAR(20),
                                uporabnisko_ime CHAR(20),
                                telefonska_stevilka CHAR(20)
                             )"""
            )

        self.parser = reqparse.RequestParser()
        self.parser.add_argument(
            "id", type=int, required=True, help="ID naročnika je obvezen"
        )
        self.parser.add_argument(
            "ime", type=str, required=True, help="Ime naročnika je obvezen"
        )
        self.parser.add_argument(
            "priimek", type=str, required=True, help="Priimek naročnika je obvezen"
        )
        self.parser.add_argument(
            "ocena", type=str, required=True, help="Ocena naročnika je obvezna"
        )
        self.parser.add_argument(
            "uporabnisko_ime",
            type=str,
            required=True,
            help="Uporabniško ime naročnika je obvezen",
        )
        self.parser.add_argument(
            "telefonska_stevilka",
            type=str,
            help="Telefonska številka naročnika je obvezna",
        )

        super(ListNarocnikov, self).__init__(*args, **kwargs)

    @ns.marshal_list_with(narocnikiApiModel)
    @ns.doc("Vrni vse narocnike")
    def get(self):
        """
        Vrni vse narocnike
        """
        l.info(
            "Zahtevaj vse narocnike",
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "get",
                "directions": "in",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": None,
                "http_code": None,
            },
        )
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
                id=ds[d]["id"],
                ime=ds[d]["ime"].strip(),
                priimek=ds[d]["priimek"].strip(),
                ocena=ds[d]["ocena"].strip(),
                uporabnisko_ime=ds[d]["uporabnisko_ime"].strip(),
                telefonska_stevilka=ds[d]["telefonska_stevilka"].strip(),
            )
            narocniki.append(narocnik)

        l.info(
            "Vrni vse narocnike",
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "get",
                "directions": "out",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": "success",
                "http_code": 200,
            },
        )

        return {"narocniki": narocniki}, 200

    @marshal_with(narocnikApiModel)
    @ns.expect(narocnikApiModel)
    @ns.doc("Dodaj narocnika")
    def post(self):
        """
        Dodaj novega narocnika
        """
        l.info(
            "Dodaj novega narocnika",
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "post",
                "directions": "in",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": None,
                "http_code": None,
            },
        )
        args = self.parser.parse_args()
        values = []
        for a in args.values():
            values.append(a)
        self.cur.execute(
            """INSERT INTO {0} (id, ime, priimek, ocena, uporabnisko_ime, telefonska_stevilka)
                VALUES ({1}, '{2}', '{3}', '{4}', '{5}', '{6}')""".format(
                "narocniki", *values
            )
        )
        self.conn.commit()
        narocnik = NarocnikModel(
            id=args["id"],
            ime=args["ime"].strip(),
            priimek=args["priimek"].strip(),
            ocena=args["ocena"].strip(),
            uporabnisko_ime=args["uporabnisko_ime"].strip(),
            telefonska_stevilka=args["telefonska_stevilka"].strip(),
        )

        l.info(
            "Nov narocnik dodan",
            extra={
                "name_of_service": "Uporabniki",
                "crud_method": "post",
                "directions": "out",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": "success",
                "http_code": 201,
            },
        )

        return narocnik, 201


class LestvicaUporabnikov(Resource):
    def __init__(self, *args, **kwargs):
        self.table_name = "narocniki"
        self.conn = connect_to_database()
        self.cur = self.conn.cursor()
        self.cur.execute(
            "select exists(select * from information_schema.tables where table_name=%s)",
            (self.table_name,),
        )
        if self.cur.fetchone()[0]:
            print("Table {0} already exists".format(self.table_name))
        else:
            self.cur.execute(
                """CREATE TABLE narocniki (
                                id INT NOT NULL,
                                ime CHAR(20),
                                priimek CHAR(20),
                                ocena CHAR(20),
                                uporabnisko_ime CHAR(20),
                                telefonska_stevilka CHAR(20)
                             )"""
            )
        super(LestvicaUporabnikov, self).__init__(*args, **kwargs)

    @ns.marshal_list_with(oceneApiModel)
    @ns.doc("Vrni lestvico narocnikov")
    def get(self):
        """
        Vrni lestvico narocnikov
        """
        l.info(
            "Zahtevaj lestvico narocnikov",
            extra={
                "name_of_service": "Ocene",
                "crud_method": "get",
                "directions": "in",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": None,
                "http_code": None,
            },
        )
        self.cur.execute("SELECT * FROM narocniki")
        rows = self.cur.fetchall()
        ds = {}
        i = 0
        for row in rows:
            ds[i] = {}
            for el, k in zip(row, narocnikiPolja):
                ds[i][k] = el
            i += 1

        # Uredi jih po uspešnosti
        ds = {
            k: v
            for k, v in sorted(
                ds.items(), key=lambda item: int(item[1]["ocena"]), reverse=True
            )
        }

        lestvica = []
        i = 1
        for d in ds:
            if int(ds[d]["ocena"].strip()) != -1:
                ocena = OcenaModel(
                    id=ds[d]["id"],
                    ime=ds[d]["ime"].strip(),
                    priimek=ds[d]["priimek"].strip(),
                    ocena=ds[d]["ocena"].strip(),
                    mesto="%s.mesto" % str(i),
                )
                lestvica.append(ocena)
                i += 1

        l.info(
            "Vrni lestvico narocnikov",
            extra={
                "name_of_service": "Ocene",
                "crud_method": "get",
                "directions": "out",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": "success",
                "http_code": 200,
            },
        )

        return {"narocniki": lestvica}, 200


class Nagrajenec(Resource):
    def __init__(self, *args, **kwargs):
        self.table_name = "narocniki"
        self.conn = connect_to_database()
        self.cur = self.conn.cursor()
        self.nagrade = [
            "cokolada",
            "zastonj vožnja",
            "bonbon",
            "nakupovalni bon",
            "20% popusta na naslednji prevoz",
            "40% popusta na naslednji prevoz",
            "60% popusta na naslednji prevoz",
            "počitnice v Maroku",
        ]
        self.cur.execute(
            "select exists(select * from information_schema.tables where table_name=%s)",
            (self.table_name,),
        )
        if self.cur.fetchone()[0]:
            print("Table {0} already exists".format(self.table_name))
        else:
            self.cur.execute(
                """CREATE TABLE narocniki (
                                id INT NOT NULL,
                                ime CHAR(20),
                                priimek CHAR(20),
                                ocena CHAR(20),
                                uporabnisko_ime CHAR(20),
                                telefonska_stevilka CHAR(20)
                             )"""
            )
        super(Nagrajenec, self).__init__(*args, **kwargs)

    @ns.marshal_list_with(nagradaApiModel)
    @ns.doc("Vrni nagrajenca")
    def get(self):
        """
        Vrni nagrajenca 
        """
        l.info(
            "Izžrebaj nagrajenca",
            extra={
                "name_of_service": "Ocene",
                "crud_method": "get",
                "directions": "in",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": None,
                "http_code": None,
            },
        )
        self.cur.execute("SELECT * FROM narocniki")
        rows = self.cur.fetchall()
        ds = {}
        i = 0
        for row in rows:
            ds[i] = {}
            for el, k in zip(row, narocnikiPolja):
                ds[i][k] = el
            i += 1

        na = random.choice(self.nagrade)
        # Uredi jih po uspešnosti
        d = random.choice(list(ds.values()))

        nagrada = NagradaModel(
            id=d["id"], ime=d["ime"].strip(), priimek=d["priimek"].strip(), nagrada=na
        )

        l.info(
            "Vrni nagrajenca",
            extra={
                "name_of_service": "Ocene",
                "crud_method": "get",
                "directions": "out",
                "ip_node": socket.gethostbyname(socket.gethostname()),
                "status": "success",
                "http_code": 200,
            },
        )

        return nagrada, 200


health = HealthCheck()
envdump = EnvironmentDump()
health.add_check(check_database_connection)
envdump.add_section("application", application_data)
app.add_url_rule("/healthcheck", "healthcheck", view_func=lambda: health.run())
app.add_url_rule("/environment", "environment", view_func=lambda: envdump.run())
api.add_resource(ListNarocnikov, "/narocniki")
api.add_resource(LestvicaUporabnikov, "/lestvica")
api.add_resource(Nagrajenec, "/loto")
api.add_resource(Narocnik, "/narocniki/<int:id>")
l.info(
    "Uporabniki App pripravljen",
    extra={
        "name_of_service": "Uporabniki",
        "crud_method": None,
        "directions": None,
        "ip_node": None,
        "status": None,
        "http_code": None,
    },
)

app.run(host="0.0.0.0", port=5003)
h.close()
