import bigfixREST
import argparse
import ipaddress
import graphviz

parser = argparse.ArgumentParser()
parser.add_argument("-s", "--bfserver", type=str, help="BigFix REST Server name/IP address", required=True)
parser.add_argument("-p", "--bfport", type=int, help="BigFix Port number (default 52311)", default=52311)
parser.add_argument("-U", "--bfuser", type=str, help="BigFix Console/REST User name", required=True)
parser.add_argument("-P", "--bfpass", type=str, help="BigFix Console/REST Password", required=True)
parser.add_argument("-g", "--groupProperty", type=str, 
    help="Name of BigFix Computer Property to group/count on", default="Subnet Address")
parser.add_argument('-m', "--map", type=str, 
    help="Relay name map fromName:toName[,fromName:toName...]")
parser.add_argument("-d", "--detail", action='store_true', help="Create nodes for each endpoint")
conf = parser.parse_args()

# First, pull all the "registration servers"
# We have to query separately because we need the root and relays in place first
# so we can assign regular endpoints to them as we process them. So two queries.
treeme = f'''(id of it, name of it, 
last report time of it, relay server flag of it, 
root server flag of it, relay server of it,
concatenation "|" of (ip addresses of it as string),
concatenation "|" of 
values of property results whose (name of property of it = "{conf.groupProperty}") of it
) 
of bes computers whose (relay server flag of it or root server flag of it)
'''.strip()

# Now pull all the "regular" endpoints
compme = f'''(id of it, name of it, 
last report time of it, relay server flag of it, 
root server flag of it, relay server of it,
concatenation "|" of (ip addresses of it as string),
concatenation "|" of 
values of property results whose (name of property of it = "{conf.groupProperty}") of it
) 
of bes computers whose (not relay server flag of it and not root server flag of it)
'''.strip()

# Initialize the relay map
rMap = {}

for mapval in str(conf.map).split(","):
    name, value = mapval.split(":")
    rMap[name] = value

bf = bigfixREST.bigfixRESTConnection(conf.bfserver, int(conf.bfport), conf.bfuser, conf.bfpass)

rqr = bf.srQueryJson(treeme)
cqr = bf.srQueryJson(compme)

compList = rqr['result'] + cqr['result']

print(cqr)

# This will hold a dictionary of relay names
relay = {}
# This will hold a dictionary of IP Addresses that refer to the same 
# relay "objects" as the relay dict. We call this "ipIdx", but it will use
# unique values of whatever BigFix computer property you use as the -g 
# command line switch.
ipIdx = {}

root = None

for comp in compList:
    if comp[4] == True:
        # This is the root server
        print("*****ROOT*****")
        root = comp[1]
        relay[root] = {}
        relay[root]['comp'] = comp
        relay[root]['count'] = 1
        relay[root]['groups'] = {}
        # Root is its own parent (I decided)
        relay[root]['parent'] = comp[1]
        for ip in str(comp[6]).split("|"):
            ipIdx[ip] = relay[root]
    elif comp[3] == True:
        # This is a relay
        print("------------> RELAY")
        rhost = comp[1]
        relay[rhost] = {}
        relay[rhost]['comp'] = comp
        relay[rhost]['count'] = 1
        relay[rhost]['groups'] = {}
        relay[rhost]['parent'] = str(comp[5]).removesuffix(f":{conf.bfport}")
        for ip in str(comp[6]).split("|"):
            ipIdx[ip] = relay[rhost]
    else:
        # This is an endpoint
        print("endpoint <-------------")
        print(comp)
        # First, find the endpoint's relay
        rName = str(comp[5]).removesuffix(f":{conf.bfport}")

        # See if we have an ip address on our hands
        try:
            ip = ipaddress.ip_address(rName)
        except ValueError:
            ip = None

        # if we do not, see if we have domain suffix on the host name
        if not ip:
            if rName.find(".") > 0:
                rName = rName[0:rName.find(".")]

        epRelay = None

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
                print("Relay not found")

        # If we could not find the relay, we must skip the endpoint
        if (epRelay == None):
            print(f"Warning: We could not locate the relay {rName} using name or IP address")
            continue

        # Increment the unique count
        epRelay['count'] += 1

        for grp in str(comp[7]).split("|"):
            if grp in epRelay['groups'].keys():
                epRelay['groups'][grp]['count'] += 1
                epRelay['groups'][grp]['compList'] += [comp]
            else:
                epRelay['groups'][grp] = {'count' : 1,
                    'compList' : [comp] }
        
## AT THIS POINT we have a recursive data structure containing all the relays in
## the deployment with all the endpoints attached to them, grouped by the grouping
## property. Let's start rendering with graphviz

dot = graphviz.Digraph(conf.bfserver + ":" + str(conf.bfport))
dot.attr(concentrate="true", fontsize="8", nodesep="0.2", ranksep="1.0", ratio="auto", rankdir="BT" )

for r in relay.keys():
    rly = relay[r]
    dot.node(r, shape="box3d", label=f"{r} - {rly['count']} unique endpoints")
    dot.edge(r, rly['parent'])
    for c in rly['groups'].keys():
        grp = rly['groups'][c]
        dot.node(c, label=f"Subnet {c} - {grp['count']} endpoints", shape="box")
        dot.edge(c, r)
        ## Detail means a node for every endpoint
        if conf.detail:
            for ep in grp['compList']:
                dot.node(ep[1], shape="component")
                dot.edge(ep[1], r)

dot.unflatten(stagger=3).render("DeploymentMap")
