# bigfix-deployment-grapher

This project will graph the relay relationships in a BigFix deployment,
providing a roll-up of endpoints grouped by an arbitrary computer property,
including counts.

It also has options for plotting all the endpoints, resulting in a larger
and busier graph. This is very much a work in progress, as it depends on
graphviz (https://graphviz.org/download/), which is a standard package
on most Linux systems and is available as a binary install on Windows.
This will need the grpahviz "dot" tool (and others depending on features you
try) to be on your PATH, so I recommend you choose that option on install.

As of the last update to this README, these are the supported command line
switches and flags:

~~~
usage: BFDeploymentMap.exe [-h] [-s BFSERVER] [-p BFPORT] [-U BFUSER]
 [-P BFPASS] [-w WRITEJSON] [-j JSON] [-o OUTPUT] [-e ENGINE]
 [-f FORMAT] [-g GROUPPROPERTY] [-m MAP] [-r] [-d]

optional arguments:
  -h, --help            show this help message and exit
  -s BFSERVER, --bfserver BFSERVER
                        BigFix REST Server name/IP address
  -p BFPORT, --bfport BFPORT
                        BigFix Port number (default 52311)
  -U BFUSER, --bfuser BFUSER
                        BigFix Console/REST User name
  -P BFPASS, --bfpass BFPASS
                        BigFix Console/REST Password
  -w WRITEJSON, --writejson WRITEJSON
                        Write query results to json file for reuse.
  -j JSON, --json JSON  Use JSON from previous run instead of doing REST query
  -o OUTPUT, --output OUTPUT
                        Output file base name
  -e ENGINE, --engine ENGINE
                        Specify the graphviz layout engine (dot, neato, etc.)
  -f FORMAT, --format FORMAT
                        Specify the output format
  -g GROUPPROPERTY, --groupProperty GROUPPROPERTY
                        Name of BigFix Computer Property to group/count on
  -m MAP, --map MAP     Relay name map fromName:toName[,fromName:toName...]
  -r, --relaysonly      Render relays only
  -d, --detail          Create nodes for each endpoint
~~~
