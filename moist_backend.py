import json
import os
import time
import argparse
import serial
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
parser.add_argument("--clean_db")
parser.add_argument("--clean_params")
parser.add_argument("--rundir", default="/home/moist/moist_rundir")
# comm
parser.add_argument("--serial_address", default="/dev/ttyACM0")
parser.add_argument("--serial_baud", default=9600)
parser.add_argument("--max_n_sensors", default=6)
# db
parser.add_argument("--db_platform", default="mariadb")
parser.add_argument("--db_host", default="localhost")
parser.add_argument("--db_port", default=3306)
parser.add_argument("--db_user", default="moist")
parser.add_argument("--db_password", default="moisture")
parser.add_argument("--db_database", default="moist")
args = parser.parse_args()


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def log(s):
    print(f"{now()}    {s}")


log(f"running at {args.rundir}")

os.makedirs(args.rundir, exist_ok=True)
log(f"running at {args.rundir}")

if args.db_platform == "mariadb":
    log("running with mariadb")
    import mariadb


def run_db_query_mariadb(query, query_args=None):
    try:
        conn = mariadb.connect(
            host=args.db_host,
            port=args.db_port,
            user=args.db_user,
            passwd=args.db_password,
            database=args.db_database
        )
    except mariadb.Error as error:
        log("Error connecting to MariaDB Platform")
        log(f"{error=}")
        return False

    cur = conn.cursor()

    try:
        if query_args is None:
            cur.execute(query)
        else:
            cur.execute(query, query_args)
    except mariadb.Error as error:
        log("Error executing query in MariaDB database")
        log(f"{error=}")
        return False

    conn.commit()
    conn.close()
    return True


def init_db(n_sensors_max):
    if n_sensors_max < 1:
        log(f"Unable to init db with {n_sensors_max=}")
        return False
    if args.db_platform == "mariadb":
        query = "CREATE TABLE IF NOT EXISTS moist_measurements (time DATETIME, event TEXT" + "".join([f", sensor_{s_idx} FLOAT" for s_idx in range(n_sensors_max)]) + ")"
        log(f"Initializing db with {query=}")
        return run_db_query_mariadb(query)
    log(f"Unknown {args.db_platform=}")
    return False


def clear_db():
    if args.db_platform == "mariadb":
        query = "DROP TABLE IF EXISTS moist_measurements"
        return run_db_query_mariadb(query)
    log(f"Unknown {args.db_platform=}")
    return False


def db_store_measurements(measurements):
    if args.db_platform == "mariadb":
        query = "INSERT INTO moist_measurements (time, event" + "".join([f", sensor_{m_val[0]}" for m_val in measurements]) + ") VALUES (?, ?" + "".join(["?" for m_val in measurements]) + ")"
        query_args = [datetime.now(), 'entry', *[m_val[1] for m_val in measurements]]
        log(f"Inserting into db with {query=}")
        log(f"Inserting into db with {query_args=}")
        return run_db_query_mariadb(query, query_args)
    log(f"Unknown {args.db_platform=}")
    return False


# settings
def default_params():
    params = {
        "loop_delay_seconds": 10
    }
    return params


def clear_params():
    json_path = os.path.join(args.rundir, "settings.json")
    if os.path.exists(json_path):
        os.remove(json_path)
        log("successfully removed params file")
        return True
    log("params file does not exist, no change")
    return False


def get_params():
    json_path = os.path.join(args.rundir, "settings.json")
    try:
        with open(json_path, "r") as f:
            params = json.load(f)
    except Exception as error:
        log(f"no params found at path {json_path}, loading defaults")
        log(f"{error=}")
        params = default_params()
        try:
            with open(json_path, "w") as f:
                json.dump(params, f, indent=4)
            log(f"saved params to json at path {json_path}")
        except Exception as error:
            log(f"could not save params to json at path {json_path}")
            log(f"{error=}")
    return params


if __name__ == "__main__":
    if args.clean_db is not None:
        log("executing db clear")
        query_result = clear_db()
        if not query_result:
            log("unable to execute db clear query")
    if args.clean_params is not None:
        log("executing params clear")
        clear_params()

    # initialize db
    query_status = False
    log("initializing database")
    while not query_status:
        query_status = init_db(args.max_n_sensors)
        if query_status:
            break
        else:
            log("unable to initialized database, retrying in 5 seconds")
        time.sleep(5)
    log("database successfully initialized")
    
    params = None
    serial_com = serial.Serial('/dev/ttyACM0', 9600)
    serial_com.reset_input_buffer()
    
    last_send = None
    awaiting_reply = False
    
    while True:
        # output to arduino
        if (not awaiting_reply) and (last_send is None or (time.time() - last_send >= params["loop_delay_seconds"])):
            last_send = time.time()
            serial_com.write(b'1')
            awaiting_reply = True

            # load params at every cycle in case something changed
            new_params = None
            while new_params is None:
                new_params = get_params()
                if new_params is not None:  # could retrieve new params
                    params = new_params
                    break
                elif params is not None:  # could not retrieve but can run on older params
                    log("unable to retrieve new params, running on old params")
                    break
                else:  # no params at all: waiting until params are found
                    log("unable to retrieve params, retrying in 5 seconds")
                    time.sleep(5)

        # input
        if serial_com.in_waiting > 0:
            awaiting_reply = False
            rcom = serial_com.readline().decode('utf-8').rstrip()

            # decode readings
            readings = rcom.split(" ")
            measurements = []
            for reading in readings:
                reading_sensor, reading_measure = reading.split(":")
                measurements.append([reading_sensor, reading_measure])
    
            # store new temperature measurements
            query_status = db_store_measurements(measurements)
            if not query_status:
                log("unable to store measurements in database")
