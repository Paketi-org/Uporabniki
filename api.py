from flask import Flask
from flask_restful import Resource, Api, reqparse, abort, marshal, fields
from configparser import ConfigParser
import psycopg2 as pg
from psycopg2 import extensions
from healthcheck import HealthCheck, EnvironmentDump

def create_app():
    app = Flask(__name__)
    api = Api(app)
    health = HealthCheck()
    envdump = EnvironmentDump()
    health.add_check(check_database_connection)
    envdump.add_section("application", application_data)
    app.add_url_rule("/healthcheck", "healthcheck", view_func=lambda: health.run())
    app.add_url_rule("/environment", "environment", view_func=lambda: envdump.run())
    api.add_resource(ListNarocnikov, "/narocniki")
    api.add_resource(Narocnik, "/narocniki/<int:id>")

    return app

def get_config(config_file, section):
    parser = ConfigParser()
    parser.read(config_file)
    db = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db[param[0]] = param[1]
    else:
        raise Exception('Section {0} not found in the {1} file'.format(section, config_file))

    return db

def check_database_connection():
    db = get_config('database.ini', 'postgresql')
    conn = pg.connect(**db)
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
    def __init__(self, config_file='database.ini', section='postgresql'):
        self.table_name = 'narocniki'
        self.db = get_config(config_file, section)
        self.conn = pg.connect(**self.db)
        self.cur = self.conn.cursor()

        self.parser = reqparse.RequestParser()
        self.parser.add_argument("id", type=int)
        self.parser.add_argument("ime", type=str)
        self.parser.add_argument("priimek", type=str)
        self.parser.add_argument("uporabnisko_ime", type=str)
        self.parser.add_argument("telefonska_stevilka", type=str)

        super(Narocnik, self).__init__()

    def get(self, id):
        self.cur.execute("SELECT * FROM narocniki WHERE id = %s" % str(id))
        row = self.cur.fetchall()

        if(len(row) == 0):
            abort(404)

        d = {}
        for el, k in zip(row[0], narocnikiPolja):
            d[k] = el

        return{"narocnik": marshal(d, narocnikiPolja)}

    def delete(self, id):
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
    def __init__(self, config_file='database.ini', section='postgresql'):
        self.table_name = 'narocniki'
        self.db = get_config(config_file, section)
        self.conn = pg.connect(**self.db)
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
        self.parser.add_argument("id", type=int)
        self.parser.add_argument("ime", type=str)
        self.parser.add_argument("priimek", type=str)
        self.parser.add_argument("uporabnisko_ime", type=str)
        self.parser.add_argument("telefonska_stevilka", type=str)

    def get(self):
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
    app.run(host="0.0.0.0", port=5000)
