"""
bigfixREST.py - I started writing a general purpose BigFix REST API
wrapper before I realized one exists. FIXME: This should be eliminated
and replaced with the pip module "besapi" at some point.

See: https://pypi.org/project/besapi/
"""
from urllib.error import HTTPError
import json
import xml.etree.ElementTree as ET
import requests

# This is here ONLY to suppress self-signed certoficate warnings
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# End of warning supression


## bigFixActionResult class
class BigfixActionResult:
    """
    BigFixActionResult - A class representing the result of a
    BigFix API /api/action POST
    """

    def __init__(self, resxml):
        self.xml = resxml
        self.root = ET.fromstring(resxml)

    def get_action_id(self):
        thing = self.root.findall("Action/ID")
        a_id = thing[0].text
        return a_id

    def get_action_url(self):
        thing = self.root.findall("Action")
        attrs = thing[0].attrib
        return attrs["Resource"]

    def get_action_result_xml(self):
        return self.xml


## bigfixRESTConnection class
class BigfixRESTConnection:
    """
    BigFixRESTConnection - A class that represents one network connection
    to one BigFix Root Server REST API
    """

    def __init__(self, bfserver, bfport, bfuser, bfpass):
        self.bfserver = bfserver
        self.bfport = bfport
        self.bfuser = bfuser
        self.bfpass = bfpass
        self.sess = requests.Session()
        self.url = f"https://{self.bfserver}:{str(self.bfport)}"

        self.sess.auth = (self.bfuser, self.bfpass)
        auth_url = f"{self.url}/api/login"
        resp = self.sess.get(auth_url, verify=False)
        if resp.status_code < 200 or resp.status_code > 299:
            raise HTTPError

    def sess_relevance_query_json(self, srquery):
        qheader = {"Content-Type": "application/x-www-form-urlencoded"}

        qquery = {"relevance": srquery, "output": "json"}

        req = requests.Request(
            "POST", self.url + "/api/query", headers=qheader, data=qquery
        )

        prepped = self.sess.prepare_request(req)
        result = self.sess.send(prepped, verify=False)

        if result.status_code == 200:
            ret_val = json.loads(result.text)
            ret_val["query"] = srquery
            return ret_val

        return None

    # The idea of this stub method is that we can parse up the return tuple, mangling the
    # relevance property names to single tokens, and then returning an array of dictionaries,
    # each row of which contains a "row" entry with a flat array and a "dict" entry with
    # the mangled names and values. Usually when you write a relevance query, you know what the
    # positions are in absolute terms. I haven't decided if this is a good idea...
    #    def flattenQueryResult(self, qres):
    #        return None

    def take_sourced_fixlet_action(
        self,
        target_list,
        site_id,
        fixlet_id,
        action_id="Action1",
        title="Programmatic Action from Python Script",
    ):
        templ = """\
<?xml version="1.0" encoding="UTF-8" ?>
<BES xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" >
<SourcedFixletAction>
	<SourceFixlet>
		<SiteID>__SiteID__</SiteID>
		<FixletID>__FixletID__</FixletID>
		<Action>__ActionID__</Action>
	</SourceFixlet>
	<Target>
        __TargetList__
	</Target>
	<Settings>
	</Settings>
	<Title>__Title__</Title>
</SourcedFixletAction>
</BES>
""".strip()

        templ = templ.replace("__SiteID__", str(site_id))
        templ = templ.replace("__FixletID__", str(fixlet_id))
        templ = templ.replace("__ActionID__", action_id)
        templ = templ.replace("__Title__", title)

        targets = ""
        for tgt in target_list:
            targets += "<ComputerName>" + tgt + "</ComputerName>\n"

        templ = templ.replace("__TargetList__", targets)

        qheader = {"Content-Type": "application/x-www-form-urlencoded"}

        req = requests.Request(
            "POST", self.url + "/api/actions", headers=qheader, data=templ
        )

        prepped = self.sess.prepare_request(req)

        result = self.sess.send(prepped, verify=False)

        if result.status_code >= 200 and result.status_code < 300:
            return BigfixActionResult(result.content)
        else:
            return None
