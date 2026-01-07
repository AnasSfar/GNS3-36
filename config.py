import json
import ipaddress
from collections import defaultdict

#lire l'intent file
with open("intentfile.json") as f:
    intent = json.load(f)
ases = intent["ases"]
routers_def = intent["routers"]
links = intent["links"]
