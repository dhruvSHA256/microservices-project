import gridfs
import pika
import json
from flask import Flask, request, send_file
from flask_pymongo import PyMongo
from auth import validate
from auth_svc import access
from storage import util
from bson.objectid import ObjectId
import sys

server = Flask(__name__)
server.config["MONGO_URI"] = "mongodb://mongodb:27017/videos"

mongo_video = PyMongo(server, uri="mongodb://mongodb:27017/videos")
mongo_mp3 = PyMongo(server, uri="mongodb://mongodb:27017/mp3s")

fs_videos = gridfs.GridFS(mongo_video.db)
fs_mp3s = gridfs.GridFS(mongo_mp3.db)

connection = pika.BlockingConnection(pika.ConnectionParameters("rabbitmq"))
channel = connection.channel()


@server.route("/login", methods=["POST"])
def login():
    token, err = access.login(request)
    if not err:
        return token
    else:
        return {"service": "Gateway", "message": f"Internal server error: {err}"}, 500


@server.route("/upload", methods=["POST"])
def upload():
    access_, err = validate.token(request)
    if err or not access_:
        return {"service": "Gateway", "message": f"Error f{err}"}, 400
    jwt_obj = json.loads(access_)
    # print(jwt_obj, file=sys.stderr)
    if jwt_obj["admin"]:
        if len(request.files) > 1 or len(request.files) < 1:
            return {"service": "Gateway", "message": "exactly one file required"}, 400
        for _, f in request.files.items():
            err = util.upload(f, fs_videos, channel, jwt_obj)
            if err:
                return err, 400
        return {"service": "Gateway", "message": "Success"}, 200
    else:
        return {"service": "Gateway", "message": "Not Authorized"}, 401


@server.route("/download", methods=["GET"])
def download():
    access_, err = validate.token(request)
    if err:
        return {"service": "Gateway", "message": f"Error f{err}"}, 400
    jwt_obj = json.loads(access_)
    if jwt_obj["admin"]:
        fid_string = request.args.get("fid")
        if not fid_string:
            return {"service": "Gateway", "message": "fid is required"}, 400
        try:
            out = fs_mp3s.get(ObjectId(fid_string))
            return send_file(out, download_name=f"{fid_string}.mp3")
        except Exception as err:
            return {"service": "Gateway", "message": f"Internal server error: {err}"}, 500

    else:
        return {"service": "Gateway", "message": "Not Authorized"}, 401


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=8080, debug=True)
