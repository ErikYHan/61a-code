from base64 import b64decode
from multiprocessing import Process, Queue

import black
import requests
from flask import jsonify, request, abort

from IGNORE_scheme_debug import Buffer, debug_eval, scheme_read, tokenize_lines
from db import connect_db
from formatter import scm_reformat


def create_language_apis(app):
    # general
    @app.route("/api/load_file/<file_name>/")
    def load_stored_file(file_name):
        with connect_db() as db:
            out = db(
                "SELECT * FROM stored_files WHERE file_name=%s;", [file_name]
            ).fetchone()
            if out:
                return out[1]
        abort(404)

    # python
    @app.route("/api/pytutor", methods=["POST"])
    def pytutor_proxy():
        response = requests.post(
            "http://pythontutor.com/web_exec_py3.py",
            data={
                "user_script": request.form["code"],
                # "options_json": r'{"cumulative_mode":true,"heap_primitives":false}',
            },
        )
        return response.text

    @app.route("/api/black", methods=["POST"])
    def black_proxy():
        try:
            return jsonify(
                {
                    "success": True,
                    "code": black.format_str(
                        request.form["code"], mode=black.FileMode()
                    )
                    + "\n",
                }
            )
        except Exception as e:
            return jsonify({"success": False, "error": repr(e)})

    # scheme
    @app.route("/api/scm_debug", methods=["POST"])
    def scm_debug():
        code = request.form["code"]
        q = Queue()
        p = Process(target=scm_worker, args=(code, q))
        p.start()
        p.join(10)
        if not q.empty():
            return jsonify(q.get())

    @app.route("/api/scm_format", methods=["POST"])
    def scm_format():
        try:
            return jsonify(
                {"success": True, "code": scm_reformat(request.form["code"])}
            )
        except Exception as e:
            return jsonify({"success": False, "error": repr(e)})

    def scm_worker(code, queue):
        try:
            buff = Buffer(tokenize_lines(code.split("\n")))
            exprs = []
            while buff.current():
                exprs.append(scheme_read(buff))
            out = debug_eval(exprs)
        except Exception as err:
            print("ParseError:", err)
            raise

        queue.put(out)

    # sql
    @app.route("/api/preloaded_tables", methods=["POST"])
    def preloaded_tables():
        try:
            with connect_db() as db:
                return jsonify(
                    {
                        "success": True,
                        "data": b64decode(
                            db("SELECT data FROM preloaded_tables").fetchone()[0]
                        ).decode("utf-8"),
                    }
                )
        except Exception as e:
            print(e)
            return jsonify({"success": False, "data": ""})