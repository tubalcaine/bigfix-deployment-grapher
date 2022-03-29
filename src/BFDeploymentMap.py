"""
BFDeploymentMap.py - A script to graph BigFix deployment using GraphViz
"""
import argparse
import ipaddress
import json
import sys
import graphviz
import bigfixREST


## BFDeploymentMap
##
## Original author: Michael Schwarz
## michael.schwarz@hcl.com
## mschwarz@multitool.net
##
## Released under the Apache 2 License
##
## A python script to generate a graph of a BigFix deployment using the widely available
## open source grpahing tool, Grpahviz (https://graphviz.org/)
## Graphviz must be installed and on the PATH for this script to work properly.
##
## Graphviz is a standard package on almost all Linux distributions, and is available
## for download for Windows, MacOS, Solaris, and FreeBSD here:
##
## https://graphviz.org/download/
##
## NB: This script (like many do) grew well beyond its original intent. For example, the -w/-j
## options to allow query results to be stored and re-used was added quite late, and its
## implementation, while okay, consisted of throwing a big if-else around an already overlong
## script.
##
## There are redundant identifiers in abundance. And as an old c/c++/Java prgorammer, I do
## not like undeclared identifiers or identifiers of module or global scope. So there
## is a lot of refactoring I'd like to do and see done. That said, this is a useful script
## so I'm putting it out there. Contact me through GitHub if you'd like to help!

parser = argparse.ArgumentParser()
parser.add_argument(
    "-s", "--bfserver", type=str, help="BigFix REST Server name/IP address"
)
parser.add_argument(
    "-p", "--bfport", type=int, help="BigFix Port number (default 52311)", default=52311
)
parser.add_argument("-U", "--bfuser", type=str, help="BigFix Console/REST User name")
parser.add_argument("-P", "--bfpass", type=str, help="BigFix Console/REST Password")
parser.add_argument(
    "-w", "--writejson", type=str, help="Write query results to json file for reuse."
)
parser.add_argument(
    "-j",
    "--json",
    type=str,
    help="Use JSON from previous run instead of doing REST query",
)
parser.add_argument(
    "-o", "--output", type=str, help="Output file base name", default="./DeploymentMap"
)
parser.add_argument(
    "-e",
    "--engine",
    type=str,
    help="Specify the graphviz layout engine (dot, neato, etc.)",
    default="dot",
)
parser.add_argument(
    "-f",
    "--format",
    type=str,
    help="Specify the output format(s) -f <fmt>[,<fmt>]",
    default="pdf",
)
parser.add_argument(
    "-g",
    "--groupProperty",
    type=str,
    help="Name of BigFix Computer Property to group/count on",
    default="Subnet Address",
)
parser.add_argument(
    "-m", "--map", type=str, help="Relay name map fromName:toName[,fromName:toName...]"
)
parser.add_argument(
    "-r", "--relaysonly", action="store_true", help="Render relays only"
)
parser.add_argument(
    "-d", "--detail", action="store_true", help="Create nodes for each endpoint"
)

conf = parser.parse_args()

if not conf.json and (not conf.bfserver or not conf.bfuser or not conf.bfpass):
    parser.error("You must specify either --json or the BigFix REST parameters\n")


# A hash to store configuration parameters needed when using -j instead of queries
# NB: This is a refactor candidate.
cnf = {}
### The BIG switch: Are we reading a JSON file, or running a query?

if conf.json:
    with open(conf.json, "r", encoding="utf-8") as jsonfh:
        jd = json.load(jsonfh)
        relay = jd["relay"]
        cnf = jd["cnf"]
else:
    ## First, move arguments we need persisted in json into cnf
    cnf["bfserver"] = conf.bfserver
    cnf["bfport"] = conf.bfport

    # First, pull all the "registration servers"
    # We have to query separately because we need the root and relays in place first
    # so we can assign regular endpoints to them as we process them. So two queries.
    treeme = f"""(id of it, name of it as lowercase,
    last report time of it, relay server flag of it, 
    root server flag of it, relay server of it as lowercase,
    concatenation "|" of (ip addresses of it as string),
    concatenation "|" of 
    values of property results whose (name of property of it = "{conf.groupProperty}") of it
    ) 
    of bes computers whose (relay server flag of it or root server flag of it)
    """.strip()

    # Now pull all the "regular" endpoints
    compme = f"""(id of it, name of it as lowercase,
    last report time of it, relay server flag of it, 
    root server flag of it, relay server of it as lowercase,
    concatenation "|" of (ip addresses of it as string),
    concatenation "|" of 
    values of property results whose (name of property of it = "{conf.groupProperty}") of it
    ) 
    of bes computers whose (not relay server flag of it and not root server flag of it)
    """.strip()

    # Initialize the relay map
    rMap = {}

    if conf.map:
        for mapval in str(conf.map).split(","):
            name, value = mapval.split(":")
            rMap[name] = value

    ## Must have EITHER --json or --bfserver
    bf = bigfixREST.BigfixRESTConnection(
        conf.bfserver, int(conf.bfport), conf.bfuser, conf.bfpass
    )

    rqr = bf.sess_relevance_query_json(treeme)

    # The relaysonly flag was added very late in the development
    # of this app. Surprisingly, implementing it was a lot easier than
    # planned!
    cqr = bf.sess_relevance_query_json(compme)
    compList = rqr["result"] + cqr["result"]

    # This will hold a dictionary of relay names
    relay = {}
    # This will hold a dictionary of IP Addresses that refer to the same
    # relay "objects" as the relay dict. We call this "ipIdx", but it will use
    # unique values of whatever BigFix computer property you use as the -g
    # command line switch.
    ipIdx = {}

    for comp in compList:
        if comp[4] is True:
            # This is the root server
            print("*****ROOT*****")
            root = comp[1]
            relay[root] = {}
            relay[root]["comp"] = comp
            relay[root]["count"] = 1
            relay[root]["groups"] = {}
            # Root is its own parent (I decided)
            relay[root]["parent"] = comp[1]

            for m in rMap:
                if relay[root]["parent"] == m:
                    relay[root]["parent"] = rMap[m]

            for IP in str(comp[6]).split("|"):
                ipIdx[IP] = relay[root]
        elif comp[3] is True:
            # This is a relay
            print("------------> RELAY")
            rhost = comp[1]
            relay[rhost] = {}
            relay[rhost]["comp"] = comp
            relay[rhost]["count"] = 1
            relay[rhost]["groups"] = {}
            relay[rhost]["parent"] = str(comp[5]).split(f":{conf.bfport}", maxsplit=1)[
                0
            ]
            for m in rMap:
                if relay[rhost]["parent"] == m:
                    relay[rhost]["parent"] = rMap[m]
            for IP in str(comp[6]).split("|"):
                ipIdx[IP] = relay[rhost]
        else:
            # This is an endpoint
            print("endpoint <-------------")
            print(comp)
            # First, find the endpoint's relay
            rName = str(comp[5]).split(f":{conf.bfport}", maxsplit=1)[0]

            # See if we have an ip address on our hands
            try:
                IP = ipaddress.ip_address(rName)
            except ValueError:
                IP = None

            # if we do not, see if we have domain suffix on the host name
            if not IP:
                if rName.find(".") > 0:
                    rName = rName[0 : rName.find(".")]

            if rName in relay.keys():
                # We can find the relay by name key
                epRelay = relay[rName]
            else:
                # We need to try ip addresses
                if rName in ipIdx.keys():
                    epRelay = ipIdx[rName]
                elif rName in rMap.keys():
                    epRelay = relay[rMap[rName]]
                else:
                    epRelay = None
                    print("Relay not found")

            # If we could not find the relay, we must skip the endpoint
            if epRelay is None:
                print(
                    f"Warning: We could not locate the relay {rName} using name or IP address"
                )
                continue

            # Increment the unique count
            epRelay["count"] += 1

            for grp in str(comp[7]).split("|"):
                if grp in epRelay["groups"].keys():
                    epRelay["groups"][grp]["count"] += 1
                    epRelay["groups"][grp]["compList"] += [comp]
                else:
                    epRelay["groups"][grp] = {"count": 1, "compList": [comp]}

    if conf.writejson:
        jsdata = {}
        jsdata["relay"] = relay
        jsdata["cnf"] = cnf

        with open(f"{conf.writejson}", "w", encoding="utf-8") as jsonfh:
            jsonfh.write(json.dumps(jsdata, sort_keys=True, indent=2))


## AT THIS POINT we have a recursive data structure containing all the relays in
## the deployment with all the endpoints attached to them, grouped by the grouping
## property. Let's start rendering with graphviz

dot = graphviz.Digraph(cnf["bfserver"] + ":" + str(cnf["bfport"]), engine=conf.engine)
dot.attr(concentrate="true", fontsize="14", ratio="auto", rankdir="BT")
dot.attr("node", fontsize="10.0", fontname="Arial")

for r in relay.keys():
    rly = relay[r]
    dot.node(
        r,
        color="red",
        shape="box3d",
        ## Add group parameters to the relay label.
        root=str(rly["comp"][4]),
        label=f"{r} - {rly['count']} unique endpoints\n",
    )
    dot.edge(r, rly["parent"], penwidth="1.5")

    ## Now we still query for all computers in "relaysonly" so we can get an accurate count
    if not conf.relaysonly:
        for c in rly["groups"].keys():
            grp = rly["groups"][c]
            ## Detail means a node for every endpoint
            if conf.detail:
                for ep in grp["compList"]:
                    dot.node(ep[1], color="blue", shape="component")
                    dot.edge(ep[1], r, penwidth="1.5")
            else:
                dot.node(
                    c,
                    color="green",
                    label=f"{conf.groupProperty} {c} - {grp['count']} endpoints",
                    shape="box",
                )
                dot.edge(c, r, penwidth="1.5")

# Now render into any and all requested formats
for fmt in conf.format.split(","):
    dot.unflatten(stagger=3).render(f"{conf.output}", format=fmt)

print("Done.")
sys.exit(0)
