import bigfixREST
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-s", "--bfserver", type=str, help="BigFix REST Server name/IP address", default="10.10.220.60")
parser.add_argument("-p", "--bfport", type=int, help="BigFix Port number (default 52311)", default=52311)
parser.add_argument("-U", "--bfuser", type=str, help="BigFix Console/REST User name", default="IEMAdmin")
parser.add_argument("-P", "--bfpass", type=str, help="BigFix Console/REST Password", default="BigFix@123")
parser.add_argument("-g", "--groupProperty", type=str, 
    help="Name of BigFix COmputer Property to group/count", default="Subnet Address")
conf = parser.parse_args()

# First, pull all the "registration servers"
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

bf = bigfixREST.bigfixRESTConnection(conf.bfserver, int(conf.bfport), conf.bfuser, conf.bfpass)

rqr = bf.srQueryJson(treeme)
cqr = bf.srQueryJson(compme)

compList = rqr['result'] + cqr['result']

print(cqr)

# This will hold a dictionary of relay names
relay = {}
# This will hold a dictionary of IP Addresses that refer to the same 
# relay "objects" as the relay dict.
ipIdx = {}

root = None

for comp in compList:
    if comp[4] == True:
        # This is the root server
        print("*****ROOT*****")
        root = comp[1]
        relay[root] = {}
        relay[root]['comp'] = comp
        relay[root]['groups'] = {}
        for ip in str(comp[6]).split("|"):
            ipIdx[ip] = relay[root]
    elif comp[3] == True:
        # This is a relay
        print("------------> RELAY")
        rhost = comp[1]
        relay[rhost] = {}
        relay[rhost]['comp'] = comp
        relay[rhost]['groups'] = {}
        for ip in str(comp[6]).split("|"):
            ipIdx[ip] = relay[rhost]
    else:
        # This is an endpoint
        print("endpoint <-------------")
        print(comp)

print("Done!")